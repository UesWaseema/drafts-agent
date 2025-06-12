import streamlit as st
import mysql.connector
import os
from dotenv import load_dotenv
import pandas as pd
from bs4 import BeautifulSoup
import re
import json # Added this import
from crewai import Agent, Task, Crew, Process
import litellm
from sklearn.linear_model import LogisticRegression
import numpy as np
from common import openrouter_llm # Import the custom LLM
# Turn on per-call token / cost accounting
os.environ["LITELLM_COLLECT_USAGE"] = "true"
from pprint import pprint # Added for nicer debug print
from typing import Optional
from langchain_core.agents import AgentFinish # Import AgentFinish
from utils.waiver import extract_waiver_percentage # Import the new waiver function
from save_results import persist # Import the new persist function

import crewai
from types import MappingProxyType  # stdlib

# ── legacy-field adapter for every CrewOutput variant ──────────────────────────
def _proxy_raw(self):
    """Map .result / .final_output to the .raw text (read-only)."""
    return self.raw

# handle every namespace CrewAI has used for the class
_candidates = [
    getattr(crewai, "CrewOutput", None),
    getattr(crewai, "output", {}),                    # may be a module or MappingProxy
    getattr(getattr(crewai, "models", None), "output", None),
]
for target in _candidates:
    if target is None:
        continue
    # module path → class sits inside
    if hasattr(target, "CrewOutput"):
        cls = target.CrewOutput
    # direct class instance
    elif isinstance(target, type) and target.__name__ == "CrewOutput":
        cls = target
    else:
        continue

    for attr in ("result", "final_output"):
        if not hasattr(cls, attr):
            setattr(cls, attr, property(_proxy_raw))
    # safe __str__ (only if not already set)
    if "__str__" not in cls.__dict__:
        cls.__str__ = lambda self: self.raw or "<no raw output>"

# Load environment variables from .env file
load_dotenv()

# Database connection details from environment variables
DB_HOST = os.getenv("DRAFTS_DB_HOST")
DB_USER = os.getenv("DRAFTS_DB_USER")
DB_PASSWORD = os.getenv("DRAFTS_DB_PASS")
DB_NAME = os.getenv("DRAFTS_DB_NAME") # Assuming this is the database for interspire_data

# Function to establish database connection
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except mysql.connector.Error as err:
        st.error(f"Error connecting to database: {err}")
        return None

def save_token_usage(conn, analysis_id, campaign_id,
                     in_tok, out_tok, cache_hits, charge):
    q = """
    INSERT INTO interspire_token_usage
            (analysis_id, campaign_id,
             input_tokens, output_tokens, cache_hits, charge_usd)
    VALUES  (%s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
             input_tokens = VALUES(input_tokens),
             output_tokens = VALUES(output_tokens),
             cache_hits   = VALUES(cache_hits),
             charge_usd   = VALUES(charge_usd),
             processed_at = CURRENT_TIMESTAMP;
    """
    with conn.cursor() as cur:
        cur.execute(q, (analysis_id, campaign_id,
                        in_tok, out_tok, cache_hits, charge))
    conn.commit()

def _collect_usage(crew: Crew) -> dict:
    """
    Aggregate token / cost data from all tasks in a CrewAI run.

    Returns a dict:
      {'prompt_tokens': int,
       'completion_tokens': int,
       'cached': int,
       'cost': float}
    Works with recent CrewAI + litellm/openrouter_llm.
    """
    totals = {"prompt_tokens": 0,
              "completion_tokens": 0,
              "cached": 0,
              "cost": 0.0}
    for t in crew.tasks:
        # 1. CrewAI ≥0.28: task.usage
        usage = getattr(t, "usage", None) or getattr(t, "result_usage", None)

        # 2. litellm fallback – usage inside last_call.response
        if not usage and hasattr(t, "last_call"):
            usage = getattr(t.last_call, "usage", None) or \
                    getattr(t.last_call, "response", {}).get("usage")

        if not usage:
            continue

        totals["prompt_tokens"]     += usage.get("prompt_tokens", 0)
        totals["completion_tokens"] += usage.get("completion_tokens", 0)
        totals["cached"]            += int(usage.get("cached", 0))
        totals["cost"]              += usage.get("cost", 0)

    return totals

# Function to clean email content
def clean_email_content(email_html):
    if not isinstance(email_html, str):
        return ""
    # Remove specific prefixes and suffixes
    prefix = "Your email client cannot read this email. To view it online, please go here: %%webversion%% Dear Dr. %%First Name%%,"
    suffix = "To stop receiving these emails:%%unsubscribelink%%"

    cleaned_html = email_html.replace(prefix, "", 1) # Replace only the first occurrence
    cleaned_html = cleaned_html.replace(suffix, "", 1) # Replace only the first occurrence
    return cleaned_html.strip()

# Email Content Analysis Functions
def extract_first_paragraph_text(html_content):
    if not isinstance(html_content, str):
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    first_p = soup.find('p')
    if first_p:
        return first_p.get_text()
    return ""

def calculate_intro_word_count(html_content):
    text = extract_first_paragraph_text(html_content)
    return len(text.split())

def calculate_intro_score_contribution(word_count):
    return 20 if word_count <= 40 else 0

def detect_bullets_position(html_content):
    if not isinstance(html_content, str):
        return "none"
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Get all top-level elements in the body to determine their order
    elements_in_order = []
    if soup.body:
        for child in soup.body.children:
            if child.name: # Only consider actual tags
                elements_in_order.append(child)

    p_indices = [i for i, tag in enumerate(elements_in_order) if tag.name == 'p']
    list_indices = [i for i, tag in enumerate(elements_in_order) if tag.name in ['ul', 'ol']]

    if len(p_indices) < 2:
        return "none"

    # Check for lists between first and second paragraphs
    for list_idx in list_indices:
        if p_indices[0] < list_idx < p_indices[1]:
            return "case 1"

    if len(p_indices) < 3:
        return "none"

    # Check for lists between second and third paragraphs
    for list_idx in list_indices:
        if p_indices[1] < list_idx < p_indices[2]:
            return "case 2"

    return "none"

def calculate_bullets_score_contribution(bullets_position):
    if bullets_position == "case 1":
        return 15
    elif bullets_position == "case 2":
        return 7.5
    return 0

# Define common CTA keywords and patterns
CTA_KEYWORDS = [
    "click here", "learn more", "buy now", "shop now", "sign up", "register",
    "download", "get started", "join now", "subscribe", "donate", "apply now",
    "contact us", "discover more", "read more", "view more", "explore", "get your"
]

def count_cta_elements(html_content):
    if not isinstance(html_content, str):
        return 0
    soup = BeautifulSoup(html_content, 'html.parser')
    count = 0

    # Check for button tags
    count += len(soup.find_all('button'))

    # Check for anchor tags with CTA keywords
    for a_tag in soup.find_all('a'):
        link_text = a_tag.get_text().lower()
        if any(keyword in link_text for keyword in CTA_KEYWORDS):
            count += 1
        if a_tag.has_attr('href') and any(keyword in a_tag['href'].lower() for keyword in CTA_KEYWORDS):
            count += 1

    # Check for CTA phrases in general text (can be broad, might need refinement)
    text_content = soup.get_text().lower()
    for keyword in CTA_KEYWORDS:
        count += text_content.count(keyword) # Count occurrences

    return count

def calculate_cta_score_contribution(cta_count):
    return 20 if cta_count == 1 else 0

# NEW Composite Content Scoring Functions
def score_intro_hook(intro_word_count):
    return 20 if intro_word_count <= 40 else 0

def score_cta_count(cta_count):
    return 20 if cta_count == 1 else 0

def score_bullet_presence(bullets_position):
    if bullets_position == 'case 1':
        return 15
    elif bullets_position == 'case 2':
        return 7.5
    else:
        return 0

def calculate_content_score(intro_word_count, cta_count, bullets_position):
    intro_score = score_intro_hook(intro_word_count)
    cta_score = score_cta_count(cta_count)
    bullet_score = score_bullet_presence(bullets_position)
    
    # Composite score scaled to 0-100
    total_score = intro_score + cta_score + bullet_score
    # Max possible score is 20 + 20 + 15 = 55
    scaled_score = (total_score / 55) * 100
    return round(scaled_score)

# Define common spam keywords (can be expanded)
SPAM_KEYWORDS = [
    "100%","100 more please","100% effective","100% off","22mag","40oz","50% off","A better you","abduct","aboard","abuse","Acceptance","Access","Access attachment","Access file","Access for free","Access here","Access now","Access right away","accommodation","Accordingly","Accounts","accumulator","Achieve goals","acid","acquisition","Act","Act fast","Act immediately","Act now","Act now!","Act right now","Action","Action required","Activate link","Acts","Ad","addict","Additional income","Addresses","Addresses on CD","adult","Advanced health","Advanced solution","adventure","aerobic","Affordable","Affordable deal","Age gracefully","Age-defying","agency","aintree","airfare","airhead","airline","airplane","airport","ak47","album","alcohol","ale","algorithm","alkaloid","All","All natural","All natural/new","All new","All-natural","All-new","allergies","allergy","allodynia","Allowance","allowed","alter","Amazed","Amazing","Amazing benefits","Amazing deal","Amazing health offer","Amazing improvement","Amazing offer","Amazing savings","Amazing stuff","ammo","amphetamine","amuse","anaesthesia","anal","analgesia","analgesic","anarchy","anesthesia","angeldust","anonymous","ante","Antioxidant","antique","antiviral","antivirus","anul","anus","anxiety","apartment","applicant","Apply here","Apply now","Apply now!","Apply Online","appointment","apprenticeship","appz","aquarium","Aquarius","archery","archive","archivecrack","arena","Aries","armed","aroused","arrival","arse","arseface","arsehole","arthritis","arthrodesis","arthroplasty","arthroscopy","artillery","Aryan","As","As seen on","As seen on Oprah","ass","asshole","assmaster","assreamer","asswipe","asthma","Astounding","astrology","astronomy","At no cost","athlete","athletics","Attached document","Attachment","attack","Attention","ATV","Auto email removal","Avoid","Avoid bankruptcy","Avoiding","Avoids","Award","Awarding","Awards","b1g","babe","babes","Bacardi","baccarat","backdoor","backpack","baggage","ballet","band","barbecue","barbeque","Barbie","barbiturate","barf","Bargain","baseball","basketball","bastard","battery","BBQ","bdsm","Be amazed","Be healthy","Be slimmer","Be surprised","Be your own boss","beach","beacon","beaner","beastiality","beat","Become a member","beer","Before it's too late","Being a member","Believe me","Beneficial","Beneficial offer","Beneficiary","Benefit","Benefits","Benefitted","Benefitting","Best","Best bargain","Best choice","Best deal","Best deal in town","Best health","Best health advice","Best health deal","Best health discovery","Best health offer","Best health practices","Best health results","Best health solution","Best health strategies","Best health tips","Best mortgage rates","Best offer","Best offer ever","Best price","Best prices","Best quality","Best rates","Best results","Best solution","Best value","Best-kept health secret","Best-kept secret","Best-selling","bestiality","bet","Better health","Better health solutions","Better health today","Better than","Better than ever","betting","Beverage","bicycle","Big bucks","Big savings","Biggest savings","bigot","bike","Billion","bingo","bitch","bitchslap","blackbox","blackjack","blacks","blade","blockbuster","blonde","blood","bloody","blow","blowout","blunt","Body","Body fat","Body transformation","bomb","bondage","boner","bong","bonghit","Bonus","Bonus gift","boobs","booked","bookies","bookmaker","Boost","Boost health fast","Boost metabolism","Boost your","Boost your immunity","Boost your life","booty","booze","bosom","Boss","Boundaries","boundary","bourbon","boutique","bowl","bowling","boxing","Brand new pager","brawl","Breakthrough","breakthroughs","Breathtaking","brewsky","Broadway","brothel","brotherhood","browse","bsdm","Budweiser","bug","bugger","build","Build muscle","Building","builds","bukkake","Bulk","Bulk purchase","bullshit","bureau","Burn calories","Burn fat","bust","busty","but not limited to","butt","butts","Buy","Buy direct","Buy now","Buy today","Buying judgements","Buying judgments","buyout","buzzed","bypass","cabaret","cabin","Cable converter","calcar","Call","Call free","Call free/now","Call me","Call now","Call now!","Call toll-free","Calling creditors","Calls","camp","campground","camping","cams","Can we have a minute of your time?","Can you help us?","Can't live without","Cancel","Cancel at any time","Cancel now","cancellation","Cancellation required","cancer","candidate","cannabis","Cannot be combined","Cannot be combined with any other offer","canoe","Capricorn","captain","caravan","Card accepted","Cards accepted","careerbuilder","careercity","careerweb","Cash","Cash bonus","Cash Cash Cash","Cash out","Cash-out","Cashback","catch","causalgia","cavity","celeb","celebration","Certified","Certified experts","Certifies","Certify","Certifying","chalet","challenge","challenged","challenges","challenging","Chance","Chances","chapter","charter","ChatGPT","ChatGPT said:","Cheap","Cheap meds","Check","Check or money order","checkout","chick","chicks","chinaman","chink","chiva","choke","cholesterol","chronic","Cialis","cinema","circulatory","Claim","Claim now","Claim your discount","Claim your discount NOW!","Claim your prize","Claims","Claims to be legal","classic","classical","Clearance","cleavage","Click","Click below","Click here","Click me to download","Click now","Click this link","Click to get","Click to open","Click to remove","Click to view","Clinic","Clinical trial","clit","clits","Closing soon","clown","club","coach","coast","cocaine","cock","cocks","cocksucker","code","codeine","codez","coding","collaborating","collaboration","Collect","Collect child support","collection","colt","comedy","comminuted","Compare","Compare now","Compare online","Compare rates","Compete for your business","competition","complimentary","concert","condom","Confidential","Confidential deal","Confidential proposal","Confidentiality","Confidentiality on all orders","Confidentially on all orders","Congratulations","console","consolidate","Consolidate debt","Consolidate debt and credit","Consolidate your debt","constipation","Contact us immediately","Content marketing","Coors","copayment","Copy accurately","Copy DVDs","cornerstone","cornerstones","corona","Cost","Costs","cottaging","Countdown","Coupon","COVID","CPM","crack","crack","cracker","crackz","craft","craps","crash","creampie","Credit","Credit bureaus","Credit card","Credit card offers","Credit or Debit","crotch","cruise","cum","cunnilingus","cunt","cunts","Cure","Cures","currency","customs","Cutting-edge","cyberattack","cybercrime","cybersecurity","cycle","dagger","dago","dance","darkie","darky","darts","DCI","dea1","dea1s","dea1z","Deadline","Deal","Deal breaker","Deal ending soon","Dear [email address]","Dear [email/friend/somebody]","Dear [first name]","Dear [Name]","Dear beneficiary","Dear friend","Dear Sir/Madam","Dear valued customer","Debt","debug","decode","decrypt","deductible","defeat","defense","dego","denervation","denied","dental","depression","descrambler","detect","Detox","devil","diabetic","diagnosis","Diagnostic","Diagnostics","diarrhea","dick","dickhead","dicks","Diet","Diet pill","Dig up dirt on friends","digestive","digital","Digital marketing","dike","dildo","dimebag","Direct email","Direct marketing","disable","disco","discotheque","Discount","Discount offer","Discover","Discover ","discovered","discoveries","discovering","Discovers","Discovery","discus","disorder","DJ","Do it now","Do it today","dock","doctor","Doctor-approved","Doctor-recommended","Doctor's advice","Doctor’s secret","Document","doggystyle","dogmatist","Dollars","domination","Don’t delay","Don't delete","Don't hesitate","Don’t hesitate!","Don't Miss","Don’t miss","Don’t miss out","Don’t miss your chance","Don’t wait","Don't waste time","dong","dope","Dormant","Double your","Double your cash","Double your income","Double your leads","Double your wealth","downers","downline","Download attachment","Download now","Downloadable content","downloadz","Drastically reduced","Dreamcast","Drug","Drugs","drunk","dss","dssware","dumb","dumbass","dyke","dynamite","dysaesthesia","dysfunction","Earn","Easy health","Easy money","Easy solution","Easy steps","ecstacy","ecstasy","education","Effective","Effective treatment","eightball","Eligible","Eliminate","Email extractor","Email harvest","Email marketing","embark","Empower","Empowered","Empowering","Empowers","emulator","enable","encode","encrypt","End pain","endocrine","Ends tonight","Energize","Enhance","Enhance performance","Enhance your life","Enhancement","enlargo","enrollee","enthusiast","eob","epidural","equestrian","Erase","Erase wrinkles","erectile","erection","erotic","erotik","euphoria","euphoric","Evite","examination","excite","excites","exciting","Exciting opportunity","Exclusive","Exclusive access","Exclusive benefit","Exclusive benefits","Exclusive bonus","Exclusive deal","Exclusive discounts","Exclusive health access","Exclusive health discovery","Exclusive health guide","Exclusive health insights","Exclusive health offer","Exclusive health report","Exclusive health secrets","Exclusive health tips","Exclusive info","Exclusive insight","Exclusive insights","Exclusive invitation","Exclusive offer","Exclusive opportunity","Exclusive promotion","Exclusive rate","Exclusive rewards","Exclusive sale","Exclusive savings","Exclusive solution","Exclusive trial","excrete","excretion","excursion","exhibition","Expedia","Expert advice","Expert recommendation","Expert-approved","Expire","Expired","Expires","Expires today","Expiring","Expiring soon","explode","Explode your business","Explore","Explored","Explores","Exploring","explosion","exterminate","Extra","Extra cash","Extra income","Extra savings","Extract email","Extraordinary","extremist","F r e e","facesit","fag","faggot","famous","fanfics","fans","fantasies","Fantastic","Fantastic deal","Fantastic offer","fantasy","FAST","Fast acting","Fast acting cure","Fast acting remedy","Fast acting solution","Fast and easy","Fast and natural","Fast approval","Fast cash","Fast health boost","Fast health tips","Fast relief","Fast results","Fast results guaranteed","Fast results now","Fast solution","Fast viagra delivery","Fat burner","Fat burning","Fat loss","Fat loss solution","Fat melting","Feel","Feel amazing","Feel amazing fast","Feel amazing instantly","Feel amazing now","Feel better","Feel better fast","Feel better immediately","Feel better now","Feel better today","Feel confident","Feel confident now","Feel energized","Feel energized instantly","Feel energized now","Feel fantastic","Feel fantastic now","Feel fantastic today","Feel great","Feel great instantly","Feel great now","Feel great today","Feel incredible","Feel more confident","Feel refreshed","Feel refreshed instantly","Feel rejuvenated","Feel renewed","Feel revitalized","Feel stronger","Feel the difference","Feel vibrant","Feel younger","Feel younger instantly","Feel younger now","Feel younger today","Feel your best","Feel your best now","Feel youthful","Feel youthful now","Feeling","Feels","felch","felching","fellatio","Felt","femdom","ferret","ferry","festival","fetische","fetish","fi2ee","Field","Fields","File attached","filez","film","filth","Final","Final call","Final hours","Final notice","Finance","Financial","Financial advice","Financial freedom","Financial independence","Financially independent","Find out how","firearm","firewall","fishing","fisting","Fitness","Fix","Flash sale","flasher","flask","flight","flightsim","flood","fluffer","football","For free","For instant access","For just $","For just $ (amount)","For just $(insert whatever amount)","For just","For just X$","For new customers only","For only","For only XXX amount","For you","Foreclosure","foreplay","Form","fornicate","Free","Free access","Free access/money/gift","Free bonus","Free cell phone","Free consultation","Free download","Free DVD","Free evaluation","Free gift","Free grant money","Free health guide","Free hosting","Free info","Free membership","Free sample","Free shipping","Free shipping offer","Free support","Free Trial","Free!","freebase","freepic","Friend","Friendly reminder","ftpz","fucked","fudgepacker","fukka","Full refund","fury","g4y","Gain","Gain an edge","Gain benefits","Gain confidence","Gain energy","Gain health","Gain muscle","Gain muscle fast","gallery","gamble","gambling","game","GameCube","gaming","ganga","gangbang","gangbangs","ganja","garden","gassing","gay","gayboy","gaylord","Gemini","Genius","genocide","Get","Get access now","Get better fast","Get better results","Get fit","Get fit fast","Get fit quickly","Get healthy","Get healthy fast","Get healthy quick","Get in shape","Get in shape fast","Get in shape instantly","Get in shape now","Get instant access","Get it away","Get it now","Get lean","Get Money","Get more","Get now","Get out of debt","Get out of debt NOW","Get paid","Get results","Get results now","get rich quick","Get rid of","Get ripped","Get slim fast","Get started","get started now","Get strong","Get strong fast","Get strong instantly","Get stronger","Get thin","Get well fast","Get your","Get your money","Get your results","Gift card","Gift certificate","Gift included","gimp","gin","Give it away","Giveaway","Giving away","Giving it away","gizz","gizzum","glider","Glock","goal","gobbler","Gold","golf","gollywog","Good day","Good news","goodwood","gook","gourmet","Grab","gram","Great","Great deal","Great offer","Greetings","Greetings of the day","grenade","gringo","Groundbreaking","growth hormone","Guarantee","Guaranteed","Guaranteed delivery","Guaranteed deposit","Guaranteed income","Guaranteed payment","Guaranteed results","Guaranteed safe","Guaranteed satisfaction","guest","guide","gymnasium","gymnastics","gyppo","h0t","hack","hacker","hackersoftware","hackertool","hackerz","hackology","hackz","hallucinogen","hammered","hammerskin","handicap","hangover","hardcore","hash","hashish","Hassle-free","hate","Have you been turned down?","headhunter","Healing","Health","Health advantage","Health and wellness","Health benefits","Health benefits unlocked","Health boost","Health breakthrough","Health breakthroughs","Health deal","Health discovery","Health enhancement","Health enhancer","Health essentials","Health expert","Health first","Health guarantee","Health hack","Health insider","Health made easy","Health makeover","Health optimizer","Health perks","Health power","Health remedy","Health revolution","Health savings","Health secret","Health secrets revealed","Health shortcut","Health success","Health tips","Health transformation","Health trend","Health upgrade","Healthcare","Healthier","Healthy and happy","heartburn","Hello (with no name included)","Hello!","hemp","hentai","Herbal","Here","hermaphrodite","heroin","heroine","hgh","Hi there","Hidden","Hidden assets","Hidden charges","Hidden costs","Hidden fees","High score","highscore","hike","HIPAA","hire","Hitler","hiv","HMO","hoax","hoaxz","hobby","hockey","hoe","holiday","holocaust","Home","Home based","Home Based business","Home employment","Home mortgage","Home-based","Home-based business","homo","horny","horoscope","horserace","Hot deal","Hot offer","hotel","hotjob","hottest","Huge discount","Human","Human growth hormone","humidor","humor","humour","hump","hurdles","Hurry","Hurry up","Hurry, while supplies last","hustler","hydroponic","hymie","hyperaesthesia","hyperalgesia","hyperpathia","hypnotic","hypoaesthesia","icewarez","If only it were that easy","illegal","Imagine","Immediate","Immediate access","Immediate action","Immediate benefits","Immediate delivery","Immediate health boost","Immediate health solution","Immediate health upgrade","Immediate improvement","Immediate relief","Immediate results","Immediate results guaranteed","Immediate savings","Immediately","immunization","Important information","Important information regarding","Important notice","Important notification","Improve","Improve fast","Improve health","Improved","Improves","Improving","In accordance with laws","Income","Income from home","Increase","Increase energy","Increase revenue","Increase sales","Increase sales/traffic","Increase stamina","Increase traffic","Increase your chances","Increase your sales","Increased","Increases","Increasing","Incredible","Incredible deal","indoor","infantilism","inflammation","Info you requested","Information you requested","inhalant","Initial investment","inject","injury","innings","innovating","Innovation","innovators","insecure","Insider","Insider tips","Install now","Instant","Instant access","Instant cure","Instant earnings","Instant health benefit","Instant health benefits","Instant health results","Instant health secret","Instant health tips","Instant improvement","Instant income","Instant offers","Instant relief","Instant results","Instant results guaranteed","Instant success","Instant weight loss","Instant wellness","Instantly better","Instantly feel better","Instantly feel great","Instantly healthier","Insurance","Insurance Lose weight","intercourse","Internet market","Internet marketing","interview","intricacies","intricate","Investment","Investment advice","Investment decision","Invoice","iPod","Ireie","island","It's effective","It’s effective","iTunes","jackoff","JACKPOT","javelin","Jaw-dropping","jazz","jerk","jerkoff","Jew","jewelry","Jews","jizz","jizzum","job","Job alert","jobdirect","jobseeker","jobsonline","jobtrak","jockey","Join","Join billions","Join for free","Join millions","Join millions of Americans","Join now","Join thousands","Join Us","joining","joke","journey","Journey ","joy","joypad","joystick","judo","jugs","juicy","jukebox","Junk","karaoke","karate","kayak","keg","ketamine","kidnap","kill","kinky","KKK","klan","kluge","knights","knob","kraut","labia","labor","lacrosse","lager","Lambo","land","landmark","landscape","landscapes","lardass","Laser printer","Last chance","Last Day","Last minute deal","latex","laugh","leader","Leading","league","Leave","Legal","Legal notice","leisure","lesbian","lesbo","lez","liability","Libra","lick","Life","Life insurance","Life-changing","Life-changing results","Life-enhancing","Life-improving","Lifetime","Lifetime access","Lifetime deal","Limited","Limited amount","Limited availability","Limited number","Limited offer","Limited opportunity","Limited supply","limited time","Limited time deal","limited time offer","Limited time only","Limited-time offer","Limited-time only","Limited-time savings","Link","linkz","liplocked","lips","liquor","Live healthier","Loan","Loan approved","Loans","lock","lodging","Long distance phone number","Long distance phone offer","Look amazing","Look and feel better","Look and feel great","Look better now","Look better today","Look fantastic","Look fantastic now","Look great fast","Look younger","Look younger instantly","Look younger now","Lose","Lose belly fat","Lose inches","Lose inches fast","Lose pounds","Lose weight","Lose weight fast","Lose weight instantly","Lose weight spam","Lottery","Low cost","Low costs","Lower interest rate","Lower interest rates","Lower monthly payment","Lower rates","Lower your mortgage rate","lowest","Lowest insurance rates","Lowest interest rate","Lowest price","Lowest price ever","Lowest rate","Lowest rates","LSD","lubricant","lubrication","luck","luggage","lust","Luxury","Luxury car","mace","machete","Magic","Magic pill","magnum","Mail in order form","Main in order form","Maintained","Majestic","Make $","Make money","make money fast","mall","manhood","marihuana","marijuana","Mark this as not junk","Marketing","Marketing solution","Marketing solutions","martini","Mass email","massacre","Mastercard","masterpiece","masturbation","match","Maximize","Medicaid","Medical","Medical breakthrough","Medicare","Medication","Medicine","Medicines","Medigap","Medium","meds","Mega sale","Melt away","Member","Member stuff","Members","Membership","memorabilia","merger","mescaline","Message contains","Message contains disclaimer","Message from","metatarsalgia","meth","methamphetamine","milestone","milestones","militia","Million","Million dollars","Millionaire","Millions","Mind-blowing","minge","Miracle","Miracle pill","Miracles","Miraculous","misuse","MLM","modifier","modify","Moment","Moments","Money","Money 💰","Money back","Money making","Money-back","Money-making","Money-saving","Money-saving tips","Month trial offer","Monthly payment","moped","More Internet Traffic","moron","morphine","Mortgage","Mortgage rates","motel","motherfukka","motorcross","motorsport","movie","mp3","mp5","mpeg","mpeg2vcr","mrn","Multi level marketing","Multi-level marketing","multimedia","multiplayer","murder","Muscle growth","museum","music","n64","NAAWP","naked","Name","Name brand","narcotic","narrates","narrating","narration","narrative","Nascar","nasty","nationjob","Natural","Natural boost","Natural formula","Natural relief","Natural remedy","Natural solution","naughty","nazi","NBA","Near you","necklacing","necrofil","needlework","negro","nekked","netwarez","neuritis","neuropathic","Never","Never again","Never before","New","New customers only","New domain extensions","NFL","NHL","nicotine","Nigerian","nigga","nigger","nightclub","Nintendo","nip","nips","niteclub","nitrous","No age restrictions","No catch","No claim forms","No commitment","No contract","No cost","No credit check","No disappointment","No experience","No extra cost","No fees","No gimmick","No hidden","No hidden charges","No hidden costs","No hidden fees","No hidden сosts","No interest","No interests","No inventory","No investment","No investment required","No medical exams","No middleman","No more","No obligation","No obligation trial","No obligations","No payment required","No prescription needed","No questions asked","No risk","No selling","No side effects","No strings attached","No waiting","No waiting required","No-obligation","No-risk guarantee","No-risk trial","nobwit","Nominated bank account","nookie","nooky","Not intended","Not junk","not just ..... but a ....","not only ... but also...","Not scam","Not shared","Not spam","Notspam","Now","Now only","Now or never","nudity","nuke","Number 1","Number one","nurse","Nutrition","Obligation","occupation","odds","oem","off","Off everything","Off shore","offense","Offer","Offer expires","Offer expires in X days","Offer extended","Offered","Offering","Offers","Offshore","Olympic","On a budget","On sale","Once in a lifetime","Once in a lifetime deal","Once in a lifetime opportunity","Once in lifetime","Once-in-a-lifetime","One hundred percent","One hundred percent free","One hundred percent guaranteed","One time","One time mailing","One-time","Online biz opportunity","Online degree","Online income","Online job","Online marketing","Online pharmacy","Only","Only $","Only a few left","Only for today","opel","Open","Open attachment","Open file","Open this","Open this email!","Opened","openhack","Opening","Opens","opera","opiate","opium","opponent","Opportunities","Opportunity","Opt in","Opt-in","opted","optedin","optedout","optin","optout","oral","Orbitz","orchestra","Order","Order here","Order immediately","Order now","Order shipped by","Order status","Order today","Order yours today","Ordered","Ordering","Orders","Orders shipped by","Orders shipped by shopper","Organic","orgy","ORIF","osteotomy","ounce","outdoors","Outstanding","Outstanding value","Outstanding values","Outstands","overdose","overseas","p1cs","paedophile","paganism","pain","painting","pantomime","panty","parasthesia","party","passport","Password","Passwords","patch","pave","paves","paving","Pay your bills","payout","PCP","pecker","peckerwood","pee","peenis","peepshow","penetrate","penetration","penis","Penis enlargement","Pennies a day","Penny stocks","Per day/per week/per year","Per month","Perfect","Perfect body","Performance","Permanent results","Personal","pervert","peyote","Pharmaceuticals","Pharmacy","Phenomenal","Phone","photograph","photography","phreak","phreaking","phuck","phuk","physical","physician","picpost","pictures","pill","Pills","pimp","pimps","pink","pint","pioneer","pioneering","pipe","Pisces","piss","pissed","pisser","pissing","pitcher","pivotal","plane","Platform","Platforms","playboy","player","playgirl","playmate","Playstation","Please","Please open","Please read","pleasure","poem","poker","polevault","polo","poof","popper","porn","porno","pot","Potent","Potential earnings","powerline","PPO","practitioner","Pre-approved","pregnancy","Prescription","Presently","Prevent","Prevent aging","Prevented","Preventing","Prevents","Preview file","Price","Price protection","Priced","Prices","Pricing","prick","Print form signature","Print from signature","Print out and fax","Priority access","Priority mail","privacy","Private","Privately owned funds","Privileged","Prize","Prizes","pro","Problem","Problem with shipping","Problem with your order","Produced and sent out","Profit","Profits","progz","Promise","Promise you","Promised","Promises","Promising","protect","Protection","Proven","Proven health tips","Proven results","Proven system","PS2","PSX","psychedelic","pub","pubes","pubic","publisher","puke","punk","Purchase","Purchase now","Pure profit","Pure Profits","Push","pushes","Pushing","pussy","puzzle","pyramid","qualifications","quarterback","queer","Quick","Quick action","Quick and easy","Quick and easy cure","Quick and easy health","Quick and easy results","Quick and easy tips","Quick and effective","Quick and safe","Quick and safe remedy","Quick and safe results","Quick and simple","Quick boost","Quick cure","Quick energy boost","Quick fix","Quick fix solution","Quick healing","Quick health boost","Quick health improvement","Quick health relief","Quick health tips","Quick health transformation","Quick improvement","Quick recovery","Quick recovery tips","Quick relief","Quick remedy","Quick results","Quick results guaranteed","Quick success","Quick transformation","Quick turnaround","Quick upgrade","Quote","Quotes","race","racist","racket","radiation","radiculogram","radio","raft","raghead","rahowa","rail","rally","rammed","ransom","rap","rape","Rapid results","rapids","Rare","Rare opportunity","Rate","Rated","Rates","Rating","Real thing","realaudio","realjukebox","realplayer","Rebate","record","Recover your debt","Recover your debt instantly","recreation","Reduce","Reduce debt","Reduce fat","Reduce stress","Reduced","Reduces","Reducing","reefer","refi","Refinance","Refinance home","Refinanced home","Refund","Regarding","reggae","Rejuvenate","Remarkable","Remarkably","Remarking","Remedy","remote","Removal","Removal instructions","Remove","Remove wrinkles","Removes","Removes wrinkles","Renew","Renew your body","Replica watches","Request","Request now","Request today","Requests","Requires initial investment","Requires investment","reservation","reserve","Reserves the right","resin","resort","respiratory","restaurant","Restore","Restore health","Restores","restricted","Restricted information","Result","Results","Results guaranteed","resume","Reverse","Reverses","Reverses aging","Revitalize","Revolutionary","Revolutionary breakthrough","Revolutionary health","Revolutionize","Revolutionized","Revolutionizes","Revolutionizing","rhyme","riddle","rifle","riot","Risk free","Risk-free","Risk-free trial","Risked","Risking","Risks","rislas","roach","rock","rohypol","roleplay","Rolex","romantic","room","roulette","Round the world","roundtrip","rowing","rugby","rum","runner","runway","Rush","Rushed","Rushes","Rushing","S 1618","Safe","Safe and effective","Safe and natural","Safe and natural remedy","Safe and secure","Safe formula","safeguard","Safeguard notice","Sagittarius","sail","sailing","sake","Sale","Sales","Sample","samurai","sangria","Satisfaction","Satisfaction guaranteed","Save","Save $","Save €, Save €","Save big","Save big money","Save big month","Save big on health","Save big today","Save instantly","Save money","Save money"
]

# Placeholder Logistic Regression Model for Bounce Risk
# In a real application, this model would be trained on historical data.
# For demonstration, we'll create a simple model that uses subject length and caps percentage.
class BounceRiskPredictor:
    def __init__(self):
        # Initialize a simple logistic regression model
        self.model = LogisticRegression()
        # Dummy training data:
        # Features: [subject_length, subject_caps_percentage]
        # Labels: 0 (low bounce), 1 (high bounce)
        X = np.array([
            [40, 5],   # Good subject, low bounce
            [30, 10],  # Good subject, low bounce
            [60, 8],   # Good subject, low bounce
            [20, 20],  # Short, high caps, high bounce
            [70, 15],  # Long, some caps, high bounce
            [45, 30],  # Medium, high caps, high bounce
            [35, 2],   # Good subject, low bounce
            [50, 12],  # Medium, some caps, low bounce
            [25, 25],  # Short, very high caps, high bounce
            [65, 18]   # Long, high caps, high bounce
        ])
        y = np.array([0, 0, 0, 1, 1, 1, 0, 0, 1, 1])
        self.model.fit(X, y)

    def predict_bounce_risk(self, subject_length, subject_caps_percentage):
        # Predict probability of bounce (class 1)
        features = np.array([[subject_length, subject_caps_percentage]])
        # Return probability of the positive class (bounce)
        bounce_prob = self.model.predict_proba(features)[0][1]
        return round(bounce_prob * 100, 2) # Return as percentage

bounce_risk_predictor = BounceRiskPredictor()

# Define CrewAI Agents
confidence_agent = Agent(
    role='Email Content and Subject Line Analyst',
    goal='Provide a comprehensive confidence score and justification for email effectiveness',
    backstory='An expert in email marketing analytics, skilled in evaluating subject lines and content for optimal engagement and deliverability. You consider factors like subject length, capitalization, spam words, intro hook, bullet point usage, and CTA presence.',
    llm=openrouter_llm,
    verbose=True,
    allow_delegation=False
)

bounce_agent = Agent(
    role='Email Deliverability and Risk Assessor',
    goal='Assess the potential bounce risk of an email based on its characteristics',
    backstory='A specialist in email deliverability, with deep understanding of factors that lead to email bounces and how to mitigate them. You use predictive models to identify high-risk emails.',
    llm=openrouter_llm,
    verbose=True,
    allow_delegation=False,
    max_iter=10,            # ↑ allow more reasoning cycles
    max_execution_time=120  # ↑ give two full minutes
)

email_content_analyst_agent = Agent(
    role='Email Content Structure and Compliance Analyst',
    goal='Analyze email content for structure, waiver compliance, and overall quality, providing actionable recommendations.',
    backstory='An expert in email marketing best practices, legal compliance, and content optimization. You meticulously examine email structure, identify waivers, and assess content quality to ensure maximum effectiveness and adherence to regulations.',
    llm=openrouter_llm,
    verbose=True,
    allow_delegation=False
)

# NEW CrewAI Agent for Waiver Extraction
waiver_extraction_agent = Agent(
    role="Waiver-Extraction Specialist",
    goal="Given one email body, output only the numeric APC-waiver/discount percentage, or 0 if none.",
    backstory="Expert at spotting fee waivers in scholarly-publishing emails.",
    llm=openrouter_llm,
    verbose=True,
    allow_delegation=False
)

# Define CrewAI Tasks
def create_confidence_task(subject_line: str, email_content: str) -> Task:
    return Task(
        description=f"""Analyze the given email subject line and content to generate a confidence score (0-100) and a detailed justification for the score.
        Consider factors like:
        - Subject length (optimal 35-55 characters)
        - Subject capitalization (avoid excessive caps)
        - Presence of spam words (refer to common.py's SPAM_WORDS if needed, but focus on general spam indicators)
        - Intro hook effectiveness (first paragraph word count, optimal <= 40 words)
        - Bullet point usage and position (case 1: between first and second paragraph, case 2: between second and third)
        - Call to Action (CTA) presence and count (optimal 1 CTA)

        Email Subject: "{subject_line}"
        Email Content: "{email_content}"

        The justification should explain how each factor contributes to the score, providing specific examples from the email where applicable.
        Output a JSON string with "score" (int) and "justification" (string).
        Example: {{"score": 85, "justification": "Subject length is optimal (45 chars). No excessive caps. No obvious spam words. Intro hook is concise (30 words). Bullet points are well-placed (case 1). One clear CTA found."}}
        IMPORTANT: Your entire response must be a single valid JSON object. Do not include any thoughts, explanations, or extra text before or after the JSON.
        """,
        agent=confidence_agent,
        expected_output='A JSON string with "score" (int) and "justification" (string).',
        output_format="json"
    )

def create_bounce_risk_task(subject_line: str, email_content: str,
                            subject_length: int,
                            subject_caps_percentage: float) -> Task:
    return Task(
        description=f"""Given the full email below, explain in ≤75 words
        why the predicted bounce risk is high or low.

        • Subject length: {subject_length}
        • CAPS ratio: {subject_caps_percentage:.1f} %

        Email Subject:
        \"\"\"{subject_line}\"\"\"

        Full Email Body (for reference):
        \"\"\"{email_content}\"\"\"

        Output JSON → {{"bounce_risk": <float>, "explanation": "<text ≤75 words>"}}
        IMPORTANT: Your entire response must be a single valid JSON object. Do not include any thoughts, explanations, or extra text before or after the JSON.
        """,
        agent=bounce_agent,
        expected_output='json',
        output_format='json'
    )

def create_email_structure_task(email_content: str) -> Task:
    return Task(
        description=f"""Analyze the structure of the given email content. Evaluate:
        - Header/subject line effectiveness (though subject is separate, consider its implied role in structure)
        - Body content organization (use of paragraphs, headings, lists)
        - Call-to-action placement and clarity
        - Overall email formatting and readability

        Email Content: "{email_content}"

        Output a JSON string with "structure_score" (int, 0-100) and "structure_justification" (string).
        Example: {{"structure_score": 90, "structure_justification": "Well-organized with clear paragraphs and a prominent CTA at the end. Good use of bullet points for readability."}}
        IMPORTANT: Your entire response must be a single valid JSON object. Do not include any thoughts, explanations, or extra text before or after the JSON.
        """,
        agent=email_content_analyst_agent,
        expected_output='A JSON string with "structure_score" (int) and "structure_justification" (string).',
        output_format="json"
    )

def create_waiver_compliance_task(email_content: str) -> Task:
    return Task(
        description=f"""Identify and evaluate waivers/disclaimers in the given email content. Assess:
        - Presence and clarity of legal disclaimers and waivers
        - Compliance with email marketing regulations (e.g., CAN-SPAM, GDPR, CCPA - focus on general principles like clear identification, valid physical address, clear opt-out)
        - Evaluation of opt-out mechanisms (is it clear, easy to find, functional)
        - Check for required legal language (e.g., unsubscribe link, physical address)

        Based on the compliance assessment, provide a waiver_percentage (0-100) where 0 means no waiver items are present or fully non-compliant, and 100 means fully compliant, with partial values allowed.

        Email Content: "{email_content}"

        Output a JSON string with "waiver_compliance" (boolean), "waiver_percentage" (int), "compliance_details" (string), and "waiver_recommendations" (string).
        Example: {{"waiver_compliance": true, "waiver_percentage": 80, "compliance_details": "Clear unsubscribe link and physical address present. No misleading headers.", "waiver_recommendations": "Consider adding a link to privacy policy."}}
        IMPORTANT: Your entire response must be a single valid JSON object. Do not include any thoughts, explanations, or extra text before or after the JSON.
        """,
        agent=email_content_analyst_agent,
        expected_output='A JSON string with "waiver_compliance" (boolean), "waiver_percentage" (int), "compliance_details" (string), and "waiver_recommendations" (string).',
        output_format="json"
    )

def create_waiver_extraction_task(email_content: str) -> Task:
    return Task(
        description=f"""
Read the email below and extract the APC waiver / discount percentage (integer).
Return 0 if no such offer exists.

EMAIL:
```{email_content}```

Respond with exactly:
{{"waiver_percentage": <integer>}}
IMPORTANT: Your entire response must be a single valid JSON object. Do not include any thoughts, explanations, or extra text before or after the JSON.
""",
        agent=waiver_extraction_agent,
        expected_output="json",
        output_format="json"
    )

def create_content_quality_task(email_content: str) -> Task:
    return Task(
        description=f"""Assess the overall content quality of the given email. Evaluate:
        - Clarity and conciseness
        - Engagement and tone
        - Grammar, spelling, and punctuation
        - Relevance to the stated purpose (e.g., campaign_name, subject)

        Email Content: "{email_content}"

        Output a JSON string with "content_quality_score" (int, 0-100) and "content_recommendations" (string).
        Example: {{"content_quality_score": 85, "content_recommendations": "Content is clear and engaging. Minor grammatical error in the third paragraph: 'its' should be 'it's'."}}
        IMPORTANT: Your entire response must be a single valid JSON object. Do not include any thoughts, explanations, or extra text before or after the JSON.
        """,
        agent=email_content_analyst_agent,
        expected_output='A JSON string with "content_quality_score" (int) and "content_recommendations" (string).',
        output_format="json"
    )

# Scoring Functions
def calculate_subject_length_score(subject_length: int) -> int:
    if 35 <= subject_length <= 55:
        return 30
    elif subject_length < 30 or subject_length > 60:
        return -25
    return 0

def calculate_subject_caps_percentage_score(subject_line: str) -> int:
    if not isinstance(subject_line, str) or not subject_line:
        return 0
    total_chars = len(subject_line)
    uppercase_chars = sum(1 for char in subject_line if char.isupper())
    if total_chars > 0:
        caps_percentage = (uppercase_chars / total_chars) * 100
        if caps_percentage > 30:
            return -20
    return 0

def calculate_subject_spam_risk_score(subject_line: str) -> int:
    if not isinstance(subject_line, str):
        return 0
    score = 0
    subject_lower = subject_line.lower()
    for keyword in SPAM_KEYWORDS:
        if keyword in subject_lower:
            score -= 10 # Penalize for each spam keyword found
    return score

def calculate_subject_punctuation_score(subject_line: str) -> int:
    if not isinstance(subject_line, str):
        return 0
    score = 0
    exclamation_count = subject_line.count('!')
    if exclamation_count > 1:
        score -= (exclamation_count - 1) * 10 # -10 points per exclamation mark, excluding the first one
    return score

def calculate_subject_overall_score(length_score_scaled: float, caps_score_scaled: float, spam_score_scaled: float, punctuation_score_scaled: float) -> float:
    final_score = (
        0.4 * length_score_scaled +
        0.2 * caps_score_scaled +
        0.3 * spam_score_scaled +
        0.1 * punctuation_score_scaled
    )
    return max(0, min(100, final_score)) # Ensure score is between 0 and 100

def parse_crew(out: Crew) -> dict:
    """
    Returns a dict if the agent produced JSON, otherwise a dict with the raw text
    under 'raw_output'. Never raises AttributeError.
    """
    if isinstance(out, str):
        raw = out.strip()
    # Handle LangChain-style AgentFinish objects
    elif isinstance(out, AgentFinish):
        raw = str(out.return_values.get("output", "")) or str(out)
    else:
        # 1) CrewAI already parsed JSON?
        if getattr(out, "json_dict", None):
            return out.json_dict

        # 2) Fallback → raw plain-text
        raw = (getattr(out, "raw", "") or "").strip()
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # attempt to extract JSON from noisy content
        matches = re.findall(r'({.*?})', raw, re.DOTALL)
        for candidate in matches:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        return {"error": "Invalid JSON", "raw_output": raw}

# Helper functions to scale individual scores to 0-100 range
def scale_length_score(score: int) -> float:
    # Min: -25, Max: 30. Range: 55.
    return (score + 25) / 55 * 100

def scale_caps_score(score: int) -> float:
    # Min: -20, Max: 0. Range: 20.
    return (score + 20) / 20 * 100

def scale_spam_score(score: int) -> float:
    # Assuming max penalty for spam is -100 for scaling purposes (can be adjusted based on SPAM_KEYWORDS list size)
    # Min: -100, Max: 0. Range: 100.
    # Cap score at 0 for max, and -100 for min to fit scaling.
    score = max(-100, score) # Ensure score doesn't go below -100 for scaling
    return (score + 100) / 100 * 100

def scale_punctuation_score(score: int) -> float:
    # Assuming max penalty for punctuation is -50 for scaling purposes
    # Min: -50, Max: 0. Range: 50.
    score = max(-50, score) # Ensure score doesn't go below -50 for scaling
    return (score + 50) / 50 * 100

def calculate_overall_score(row):
    # weighted blend; negative weight for bounce risk
    score = (
        0.15 * row['subject_overall_score']  +
        0.15 * row['email_content_score']    +
        0.20 * row['confidence_score']       +
        0.15 * row['structure_score']        +
        0.15 * row['content_quality_score']  +
        0.20 * row['waiver_percentage']      -
        0.10 * row['bounce_risk']            # penalty
    )
    return max(0, min(100, round(score)))

# Function to fetch and process data
# @st.cache_data(ttl=600) # Cache data for 10 minutes
def get_interspire_data():
    print("-- entering get_interspire_data()")         # NEW
    conn = get_db_connection()
    print("-- got conn =", conn)                       # NEW

    if conn is None:
        return pd.DataFrame()

    try:
        query = """
        SELECT  id,
                campaign_name,
                subject,
                email,
                draft_type
                ,sent_date
        FROM    interspire_data
        WHERE   journal = 'IJN'
          AND   LOWER(draft_type) LIKE '%cfp%'
        ORDER BY
                STR_TO_DATE(
                    REGEXP_SUBSTR(campaign_name, '[0-9]{4}-[0-9]{2}-[0-9]{2}'),
                    '%Y-%m-%d'
                ) DESC
                ,sent_date DESC
        LIMIT 10;
        """
        df = pd.read_sql(query, conn)
        df['campaign_date'] = pd.to_datetime(
            df['campaign_name'].str.extract(r'(\d{4}-\d{2}-\d{2})')[0],
            errors='coerce'
        )
        df['sent_date'] = pd.to_datetime(df['sent_date'], errors='coerce')

        # Add column placeholders early
        for c in ['waiver_compliance', 'compliance_details', 'waiver_recommendations']:
            if c not in df.columns:
                df[c] = None

        # Data Transformations
        df['analysis_id'] = df.index + 1 # Auto-increment field
        df['campaign_id'] = df['id'] # Display raw data from the database
        df['subject_line'] = df['subject'] # Raw subject data with minimal cleanup
        df['subject_length'] = df['subject'].astype(str).apply(lambda x: len(x.replace(" ", ""))) # Strip whitespaces and calculate length
        df['email_content'] = df['email'].apply(clean_email_content) # Clean email content
        # Removed: df['waiver_percentage'] = df['email_content'].apply(extract_waiver_percentage)

        # Email Type
        df['email_type'] = df['draft_type'].apply(lambda x: "open" if "open" in str(x).lower() else "cfp")

        # Calculate new scoring columns
        df['subject_length_score'] = df['subject_length'].apply(calculate_subject_length_score)
        df['subject_caps_percentage'] = df['subject_line'].apply(
            lambda x: sum(1 for char in str(x) if char.isupper()) / len(str(x)) * 100 if len(str(x)) > 0 else 0
        )
        df['subject_caps_percentage_score'] = df['subject_line'].apply(calculate_subject_caps_percentage_score)
        df['subject_spam_risk_score'] = df['subject_line'].apply(calculate_subject_spam_risk_score)
        df['subject_punctuation_score'] = df['subject_line'].apply(calculate_subject_punctuation_score)

        # Calculate subject_overall_score
        df['subject_overall_score'] = df.apply(
            lambda row: calculate_subject_overall_score(
                length_score_scaled=scale_length_score(row['subject_length_score']),
                caps_score_scaled=scale_caps_score(row['subject_caps_percentage_score']),
                spam_score_scaled=scale_spam_score(row['subject_spam_risk_score']),
                punctuation_score_scaled=scale_punctuation_score(row['subject_punctuation_score'])
            ), axis=1
        )


        # Calculate new email content analysis columns
        df['intro_word_count'] = df['email_content'].apply(calculate_intro_word_count)
        df['intro_score_contribution'] = df['intro_word_count'].apply(calculate_intro_score_contribution)
        df['bullets_position'] = df['email_content'].apply(detect_bullets_position)
        df['bullets_score_contribution'] = df['bullets_position'].apply(calculate_bullets_score_contribution)
        df['cta_count'] = df['email_content'].apply(count_cta_elements)
        df['cta_score_contribution'] = df['cta_count'].apply(calculate_cta_score_contribution)

        # Calculate email_content_score
        df['email_content_score'] = df.apply(
            lambda row: calculate_content_score(
                row['intro_word_count'],
                row['cta_count'],
                row['bullets_position']
            ), axis=1
        )

        # Initialize new columns
        df['confidence_score'] = None
        df['confidence_score_justification'] = None
        df['bounce_risk'] = None
        df['bounce_risk_explanation'] = None
        df['overall_score'] = None # Before the loop create the column

        # Progress indicator in Streamlit
        progress_bar = st.progress(0, text="Starting analysis…")
        status_msg   = st.empty()
        total_rows   = len(df)
        print("-- df rows =", len(df))

        # Process each row with CrewAI and Bounce Risk Predictor
        for index, row in df.iterrows():
            status_msg.text(
                f"Processing email {index + 1} / {total_rows} (campaign ID {row['campaign_id']})"
            )
            subject_line = row['subject_line']
            email_content = row['email_content']
            subject_length = row['subject_length']
            subject_caps_percentage = row['subject_caps_percentage']

            # --- CrewAI for Confidence Score ---
            confidence_task = create_confidence_task(subject_line, email_content)
            confidence_crew = Crew(
                agents=[confidence_agent],
                tasks=[confidence_task],
                verbose=False,
                process=Process.sequential
            )
            try:
                confidence_output = confidence_crew.kickoff()
                
                # Debug Confirmation
                # print("RAW OUTPUT (Confidence):", getattr(confidence_output, "raw", confidence_output))

                confidence_result = parse_crew(confidence_output)
                
                if "error" in confidence_result:
                    st.warning(f"Error processing confidence CrewAI for row {index}: {confidence_result['error']}. Raw output: {confidence_result.get('raw_output', 'N/A')}")
                    df.at[index, 'confidence_score'] = 0
                    df.at[index, 'confidence_score_justification'] = f"Error: {confidence_result['error']}"
                else:
                    df.at[index, 'confidence_score'] = confidence_result.get('score')
                    df.at[index, 'confidence_score_justification'] = confidence_result.get('justification')
            except Exception as e:
                st.warning(f"Unexpected error running confidence CrewAI for row {index}: {e}")
                df.at[index, 'confidence_score'] = 0
                df.at[index, 'confidence_score_justification'] = f"Unexpected Error: {e}"

            # --- CrewAI for Bounce Risk Explanation (using the logistic model for score) ---
            # First, calculate the bounce risk using the local model
            calculated_bounce_risk = bounce_risk_predictor.predict_bounce_risk(
                subject_length, subject_caps_percentage
            )
            df.at[index, 'bounce_risk'] = calculated_bounce_risk

            # Then, use CrewAI to get an explanation for this calculated risk
            bounce_risk_task = create_bounce_risk_task(
                subject_line, email_content, subject_length, subject_caps_percentage
            )
            bounce_crew = Crew(
                agents=[bounce_agent],
                tasks=[bounce_risk_task],
                verbose=False,
                process=Process.sequential
            )
            # ─── run with up to 2 retries ───
            for attempt in range(3):   # 0,1,2  → 1 initial + 2 retries
                try:
                    bounce_output = bounce_crew.kickoff()
                    break              # success → exit the loop
                except Exception as e:
                    if attempt == 2:   # third failure
                        raise          # let outer try/except handle it
                    continue           # retry

            # existing parsing / try-except block stays the same
            bounce_result = parse_crew(bounce_output)
            
            if "error" in bounce_result:
                st.warning(f"Error processing bounce CrewAI for row {index}: {bounce_result['error']}. Raw output: {bounce_result.get('raw_output', 'N/A')}")
                df.at[index, 'bounce_risk_explanation'] = (
                    "Automatic note: agent exceeded limits; refer mainly to subject length "
                    f"({subject_length}) and CAPS ({subject_caps_percentage:.1f}%) for risk."
                )
            else:
                # The agent's explanation should be based on the provided subject_length and subject_caps_percentage
                df.at[index, 'bounce_risk_explanation'] = bounce_result.get('explanation')

            # --- CrewAI for Email Structure Analysis ---
            structure_task = create_email_structure_task(email_content)
            structure_crew = Crew(
                agents=[email_content_analyst_agent],
                tasks=[structure_task],
                verbose=False,
                process=Process.sequential
            )
            try:
                structure_output = structure_crew.kickoff()

                # Debug Confirmation
                # print("RAW OUTPUT (Structure):", getattr(structure_output, "raw", structure_output))

                structure_result = parse_crew(structure_output)
                
                if "error" in structure_result:
                    st.warning(f"Error processing structure CrewAI for row {index}: {structure_result['error']}. Raw output: {structure_result.get('raw_output', 'N/A')}")
                    df.at[index, 'structure_score'] = 0
                    df.at[index, 'structure_justification'] = f"Error: {structure_result['error']}"
                else:
                    df.at[index, 'structure_score'] = structure_result.get('structure_score')
                    df.at[index, 'structure_justification'] = structure_result.get('structure_justification')
            except Exception as e:
                st.warning(f"Unexpected error running structure CrewAI for row {index}: {e}")
                df.at[index, 'structure_score'] = 0
                df.at[index, 'structure_justification'] = f"Unexpected Error: {e}"

            # --- NEW CrewAI for Waiver Extraction ---
            waiver_task = create_waiver_extraction_task(email_content)
            waiver_crew = Crew(
                agents=[waiver_extraction_agent],
                tasks=[waiver_task],
                verbose=False,
                process=Process.sequential
            )

            try:
                waiver_out  = waiver_crew.kickoff()
                waiver_pct  = parse_crew(waiver_out).get("waiver_percentage", 0)
            except Exception:
                waiver_pct  = extract_waiver_percentage(email_content)  # regex fallback

            df.at[index, "waiver_percentage"] = waiver_pct

            # --- Waiver-compliance analysis ------------------------------------
            waiver_comp_task = create_waiver_compliance_task(email_content)
            waiver_comp_crew = Crew(
                agents=[email_content_analyst_agent],
                tasks=[waiver_comp_task],
                verbose=False,
                process=Process.sequential
            )

            try:
                comp_out  = waiver_comp_crew.kickoff()
                comp_json = parse_crew(comp_out)

                df.at[index, 'waiver_compliance']      = comp_json.get('waiver_compliance', False)
                df.at[index, 'compliance_details']     = comp_json.get('compliance_details', '')
                df.at[index, 'waiver_recommendations'] = comp_json.get('waiver_recommendations', '')
            except Exception as e:
                df.at[index, 'waiver_compliance']      = False
                df.at[index, 'compliance_details']     = f'Error: {e}'
                df.at[index, 'waiver_recommendations'] = f'Error: {e}'


            # --- CrewAI for Content Quality Assessment ---
            content_quality_task = create_content_quality_task(email_content)
            content_quality_crew = Crew(
                agents=[email_content_analyst_agent],
                tasks=[content_quality_task],
                verbose=False,
                process=Process.sequential
            )
            try:
                content_quality_output = content_quality_crew.kickoff()

                # Debug Confirmation
                # print("RAW OUTPUT (Content Quality):", getattr(content_quality_output, "raw", content_quality_output))

                content_quality_result = parse_crew(content_quality_output)
                
                if "error" in content_quality_result:
                    st.warning(f"Error processing content quality CrewAI for row {index}: {content_quality_result['error']}. Raw output: {content_quality_result.get('raw_output', 'N/A')}")
                    df.at[index, 'content_quality_score'] = 0
                    df.at[index, 'content_recommendations'] = f"Error: {content_quality_result['error']}"
                else:
                    df.at[index, 'content_quality_score'] = content_quality_result.get('content_quality_score')
                    df.at[index, 'content_recommendations'] = content_quality_result.get('content_recommendations')
            except Exception as e:
                st.warning(f"Unexpected error running content quality CrewAI for row {index}: {e}")
                df.at[index, 'content_quality_score'] = 0
                df.at[index, 'content_recommendations'] = f"Unexpected Error: {e}"
            
            # After all other scores are filled, but still inside the main loop:
            df.at[index, 'overall_score'] = calculate_overall_score(df.loc[index])
            
            # ── token accounting ───────────────────────────────────────────
            toks_in  = toks_out = cached = 0
            cost_usd = 0.0

            for crew in (confidence_crew, bounce_crew, structure_crew,
                         waiver_crew, waiver_comp_crew, content_quality_crew):
                u = _collect_usage(crew)
                toks_in  += u["prompt_tokens"]
                toks_out += u["completion_tokens"]
                cached   += u["cached"]
                cost_usd += u["cost"]

            # write / up-sert into ledger
            if conn:
                save_token_usage(conn,
                                 analysis_id=row['analysis_id'],
                                 campaign_id=row['campaign_id'],
                                 in_tok=toks_in,
                                 out_tok=toks_out,
                                 cache_hits=cached,
                                 charge=cost_usd)
            # ───────────────────────────────────────────────────────────────
            
            progress_bar.progress((index + 1) / total_rows)

        status_msg.empty()
        progress_bar.empty()

        # Select and reorder columns for display
        display_columns = [
            'analysis_id', 'campaign_id', 'subject_line', 'subject_length',
            'email_content', 'email_type',
            'subject_length_score', 'subject_caps_percentage', 'subject_spam_risk_score',
            'subject_punctuation_score', 'subject_overall_score',
            'intro_word_count', 'intro_score_contribution', 'bullets_position',
            'bullets_score_contribution', 'cta_count', 'cta_score_contribution',
            'email_content_score',
            'confidence_score', 'confidence_score_justification',
            'bounce_risk', 'bounce_risk_explanation',
            'structure_score', 'structure_justification',
            'waiver_percentage', 'waiver_compliance', 'compliance_details', 'waiver_recommendations', # Insert 'waiver_percentage' next to waiver_compliance
            'content_quality_score', 'content_recommendations',
            'campaign_date', 'sent_date', # Add sent_date and campaign_date to display
            'overall_score' # overall_score at the end
        ]
        df = df[display_columns]

        return df
    except Exception as e:
        st.error(f"Error fetching or processing data: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

# ──────────────────────────────────────────────────────────────
def run_app():
    st.set_page_config(layout="wide")
    st.title("Interspire Email Campaign Analysis")

    data = get_interspire_data()

    if not data.empty:
        persist(data) # Persist the data to the database
        # Display Initial Metrics
        avg_confidence = data['confidence_score'].mean() if 'confidence_score' in data.columns else 0
        avg_bounce_risk = data['bounce_risk'].mean() if 'bounce_risk' in data.columns else 0
        avg_structure_score = data['structure_score'].mean() if 'structure_score' in data.columns else 0
        avg_content_quality_score = data['content_quality_score'].mean() if 'content_quality_score' in data.columns else 0
        avg_overall = data['overall_score'].mean() if 'overall_score' in data.columns else 0 # At the top of run_app() compute:
        avg_delay = (data['campaign_date'] - data['sent_date']).dt.days.mean() if 'campaign_date' in data.columns and 'sent_date' in data.columns else 0

        col1, col2, col3, col4, col5, col6 = st.columns(6) # Adjusted to 6 columns
        with col1:
            st.metric(label="Average Confidence Score", value=f"{avg_confidence:.2f}%")
        with col2:
            st.metric(label="Average Bounce Risk", value=f"{avg_bounce_risk:.2f}%")
        
        with col3:
            st.metric(label="Average Structure Score", value=f"{avg_structure_score:.2f}%")
        with col4:
            st.metric(label="Average Content Quality", value=f"{avg_content_quality_score:.2f}%")
        with col5: # and show it as a fifth metric:
            st.metric(label="Average Overall Score", value=f"{avg_overall:.2f}%")
        with col6:
            st.metric("Avg Days From Send → Campaign", f"{avg_delay:.1f}")

        st.markdown("---") # Separator

        # Waiver Compliance Summary
        if 'waiver_compliance' in data.columns:
            compliant_count = data['waiver_compliance'].sum()
            non_compliant_count = len(data) - compliant_count
            st.subheader("Waiver Compliance Summary")
            st.info(f"**{compliant_count}** emails are compliant with waivers/disclaimers. **{non_compliant_count}** emails are non-compliant.")
            st.markdown("---") # Separator

        # Search/Filter functionality
        filtered_data = data.copy() # Create a copy to filter

        date_filter = st.sidebar.date_input(
            "Show emails sent on or after …", value=None
        )
        if date_filter:
            filtered_data = filtered_data[filtered_data['sent_date'] >= pd.Timestamp(date_filter)]

        search_term = st.text_input("Search by Campaign ID, Subject Line, or Email Type", "").lower()
        filtered_data = filtered_data[
            filtered_data['campaign_id'].astype(str).str.contains(search_term, case=False) |
            filtered_data['subject_line'].astype(str).str.contains(search_term, case=False) |
            filtered_data['email_type'].astype(str).str.contains(search_term, case=False)
        ]

        # Pagination
        page_size = st.sidebar.slider("Rows per page", 10, 100, 20)
        total_pages = (len(filtered_data) + page_size - 1) // page_size
        current_page = st.sidebar.number_input("Page", 1, total_pages, 1)

        start_index = (current_page - 1) * page_size
        end_index = start_index + page_size
        paginated_data = filtered_data.iloc[start_index:end_index]

        st.write(f"Displaying {len(paginated_data)} of {len(filtered_data)} records.")
        st.dataframe(paginated_data, use_container_width=True)
    else:
        st.info("No data to display. Please check database connection and table.")

if __name__ == "__main__":
    run_app()
