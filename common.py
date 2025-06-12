import os
import sqlite3 # Re-add sqlite3 import
import re
import json
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Any, Mapping, Optional, Union, Tuple
import logging # Import logging
from db import get_conn # Import get_conn from the new db.py
from langchain_core.language_models.llms import BaseLLM
from langchain_core.outputs import LLMResult
from litellm import completion

# Set up logger for common.py
logger = logging.getLogger(__name__)
if os.getenv('LOG_LEVEL') == 'DEBUG':
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO) # Default to INFO

# Placeholder for spam words. User will add them manually.
# These should be in lowercase for case-insensitive matching.
SPAM_WORDS = [
    "100%","100 more please","100% effective","100% off","22mag","40oz","50% off","A better you","abduct","aboard","abuse","Acceptance","Access","Access attachment","Access file","Access here","Access now","Access right away","accommodation","Accordingly","Accounts","accumulator","Achieve goals","acid","acquisition","Act","Act fast","Act immediately","Act now","Act now!","Act right now","Action","Action required","Activate link","Acts","Ad","addict","Additional income","Addresses","Addresses on CD","adult","Advanced health","Advanced solution","adventure","aerobic","Affordable","Affordable deal","Age gracefully","Age-defying","agency","aintree","airfare","airhead","airline","airplane","airport","ak47","album","alcohol","ale","algorithm","alkaloid","All","All natural","All natural/new","All new","All-natural","All-new","allergies","allergy","allodynia","Allowance","allowed","alter","Amazed","Amazing","Amazing benefits","Amazing deal","Amazing health offer","Amazing improvement","Amazing offer","Amazing savings","Amazing stuff","ammo","amphetamine","amuse","anaesthesia","anal","analgesia","analgesic","anarchy","anesthesia","angeldust","anonymous","ante","Antioxidant","antique","antiviral","antivirus","anul","anus","anxiety","apartment","applicant","Apply here","Apply now","Apply now!","Apply Online","appointment","apprenticeship","appz","aquarium","Aquarius","archery","archive","archivecrack","arena","Aries","armed","aroused","arrival","arse","arseface","arsehole","arthritis","arthrodesis","arthroplasty","arthroscopy","artillery","Aryan","As","As seen on","As seen on Oprah","ass","asshole","assmaster","assreamer","asswipe","asthma","Astounding","astrology","astronomy","At no cost","athlete","athletics","Attached document","Attachment","attack","Attention","ATV","Auto email removal","Avoid","Avoid bankruptcy","Avoiding","Avoids","Award","Awarding","Awards","b1g","babe","babes","Bacardi","baccarat","backdoor","backpack","baggage","ballet","band","barbecue","barbeque","Barbie","barbiturate","barf","Bargain","baseball","basketball","bastard","battery","BBQ","bdsm","Be amazed","Be healthy","Be slimmer","Be surprised","Be your own boss","beach","beacon","beaner","beastiality","beat","Become a member","beer","Before it's too late","Being a member","Believe me","Beneficial","Beneficial offer","Beneficiary","Benefit","Benefits","Benefitted","Benefitting","Best","Best bargain","Best choice","Best deal","Best deal in town","Best health","Best health advice","Best health deal","Best health discovery","Best health offer","Best health practices","Best health results","Best health solution","Best health strategies","Best health tips","Best mortgage rates","Best offer","Best offer ever","Best price","Best prices","Best quality","Best rates","Best results","Best solution","Best value","Best-kept health secret","Best-kept secret","Best-selling","bestiality","bet","Better health","Better health solutions","Better health today","Better than","Better than ever","betting","Beverage","bicycle","Big bucks","Big savings","Biggest savings","bigot","bike","Billion","bingo","bitch","bitchslap","blackbox","blackjack","blacks","blade","blockbuster","blonde","blood","bloody","blow","blowout","blunt","Body","Body fat","Body transformation","bomb","bondage","boner","bong","bonghit","Bonus","Bonus gift","boobs","booked","bookies","bookmaker","Boost","Boost health fast","Boost metabolism","Boost your","Boost your immunity","Boost your life","booty","booze","bosom","Boss","Boundaries","boundary","bourbon","boutique","bowl","bowling","boxing","Brand new pager","brawl","Breakthrough","breakthroughs","Breathtaking","brewsky","Broadway","brothel","brotherhood","browse","bsdm","Budweiser","bug","bugger","build","Build muscle","Building","builds","bukkake","Bulk","Bulk purchase","bullshit","bureau","Burn calories","Burn fat","bust","busty","but not limited to","butt","butts","Buy","Buy direct","Buy now","Buy today","Buying judgements","Buying judgments","buyout","buzzed","bypass","cabaret","cabin","Cable converter","calcar","Call","Call free","Call free/now","Call me","Call now","Call now!","Call toll-free","Calling creditors","Calls","camp","campground","camping","cams","Can we have a minute of your time?","Can you help us?","Can't live without","Cancel","Cancel at any time","Cancel now","cancellation","Cancellation required","cancer","candidate","cannabis","Cannot be combined","Cannot be combined with any other offer","canoe","Capricorn","captain","caravan","Card accepted","Cards accepted","careerbuilder","careercity","careerweb","Cash","Cash bonus","Cash Cash Cash","Cash out","Cash-out","Cashback","catch","causalgia","cavity","celeb","celebration","Certified","Certified experts","Certifies","Certify","Certifying","chalet","challenge","challenged","challenges","challenging","Chance","Chances","chapter","charter","ChatGPT","ChatGPT said:","Cheap","Cheap meds","Check","Check or money order","checkout","chick","chicks","chinaman","chink","chiva","choke","cholesterol","chronic","Cialis","cinema","circulatory","Claim","Claim now","Claim your discount","Claim your discount NOW!","Claim your prize","Claims","Claims to be legal","classic","classical","Clearance","cleavage","Click","Click below","Click here","Click me to download","Click now","Click this link","Click to get","Click to open","Click to remove","Click to view","Clinic","Clinical trial","clit","clits","Closing soon","clown","club","coach","coast","cocaine","cock","cocks","cocksucker","code","codeine","codez","coding","collaborating","collaboration","Collect","Collect child support","collection","colt","comedy","comminuted","Compare","Compare now","Compare online","Compare rates","Compete for your business","competition","complimentary","concert","condom","Confidential","Confidential deal","Confidential proposal","Confidentiality","Confidentiality on all orders","Confidentially on all orders","Congratulations","console","consolidate","Consolidate debt","Consolidate debt and credit","Consolidate your debt","constipation","Contact us immediately","Content marketing","Coors","copayment","Copy accurately","Copy DVDs","cornerstone","cornerstones","corona","Cost","Costs","cottaging","Countdown","Coupon","COVID","CPM","crack","cracked","cracker","crackz","craft","crank","craps","crash","creampie","Credit","Credit bureaus","Credit card","Credit card offers","Credit or Debit","crotch","cruise","cum","cunnilingus","cunt","cunts","Cure","Cures","currency","customs","Cutting-edge","cyberattack","cybercrime","cybersecurity","cycle","dagger","dago","dance","darkie","darky","darts","DCI","dea1","dea1s","dea1z","Deadline","Deal","Deal breaker","Deal ending soon","Dear [email address]","Dear [email/friend/somebody]","Dear [first name]","Dear [Name]","Dear beneficiary","Dear friend","Dear Sir/Madam","Dear valued customer","Debt","debug","decode","decrypt","deductible","defeat","defense","dego","denervation","denied","dental","depression","descrambler","detect","Detox","devil","diabetic","diagnosis","Diagnostic","Diagnostics","diarrhea","dick","dickhead","dicks","Diet","Diet pill","Dig up dirt on friends","digestive","digital","Digital marketing","dike","dildo","dimebag","Direct email","Direct marketing","disable","disco","discotheque","Discount","Discount offer","Discover","Discover ","discovered","discoveries","discovering","Discovers","Discovery","discus","disorder","DJ","Do it now","Do it today","dock","doctor","Doctor-approved","Doctor-recommended","Doctor's advice","Doctor’s secret","Document","doggystyle","dogmatist","Dollars","domination","Don’t delay","Don't delete","Don't hesitate","Don’t hesitate!","Don't Miss","Don’t miss","Don’t miss out","Don’t miss your chance","Don’t wait","Don't waste time","dong","dope","Dormant","Double your","Double your cash","Double your income","Double your leads","Double your wealth","downers","downline","Download attachment","Download now","Downloadable content","downloadz","Drastically reduced","Dreamcast","Drug","Drugs","drunk","dss","dssware","dumb","dumbass","dyke","dynamite","dysaesthesia","dysfunction","Earn","Easy health","Easy money","Easy solution","Easy steps","ecstacy","ecstasy","education","Effective","Effective treatment","eightball","Eligible","Eliminate","Email extractor","Email harvest","Email marketing","embark","Empower","Empowered","Empowering","Empowers","emulator","enable","encode","encrypt","End pain","endocrine","Ends tonight","Energize","Enhance","Enhance performance","Enhance your life","Enhancement","enlargo","enrollee","enthusiast","eob","epidural","equestrian","Erase","Erase wrinkles","erectile","erection","erotic","erotik","euphoria","euphoric","Evite","examination","excite","excites","exciting","Exciting opportunity","Exclusive","Exclusive access","Exclusive benefit","Exclusive benefits","Exclusive bonus","Exclusive deal","Exclusive discounts","Exclusive health access","Exclusive health discovery","Exclusive health guide","Exclusive health insights","Exclusive health offer","Exclusive health report","Exclusive health secrets","Exclusive health tips","Exclusive info","Exclusive insight","Exclusive insights","Exclusive invitation","Exclusive offer","Exclusive opportunity","Exclusive promotion","Exclusive rate","Exclusive rewards","Exclusive sale","Exclusive savings","Exclusive solution","Exclusive trial","excrete","excretion","excursion","exhibition","Expedia","Expert advice","Expert recommendation","Expert-approved","Expire","Expired","Expires","Expires today","Expiring","Expiring soon","explode","Explode your business","Explore","Explored","Explores","Exploring","explosion","exterminate","Extra","Extra cash","Extra income","Extra savings","Extract email","Extraordinary","extremist","F r e e","facesit","fag","faggot","famous","fanfics","fans","fantasies","Fantastic","Fantastic deal","Fantastic offer","fantasy","FAST","Fast acting","Fast acting cure","Fast acting remedy","Fast acting solution","Fast and easy","Fast and natural","Fast approval","Fast cash","Fast health boost","Fast health tips","Fast relief","Fast results","Fast results guaranteed","Fast results now","Fast solution","Fast viagra delivery","Fat burner","Fat burning","Fat loss","Fat loss solution","Fat melting","Feel","Feel amazing","Feel amazing fast","Feel amazing instantly","Feel amazing now","Feel amazing today","Feel better","Feel better fast","Feel better immediately","Feel better now","Feel better today","Feel confident","Feel confident now","Feel energized","Feel energized instantly","Feel energized now","Feel fantastic","Feel fantastic now","Feel fantastic today","Feel great","Feel great instantly","Feel great now","Feel great today","Feel incredible","Feel more confident","Feel refreshed","Feel refreshed instantly","Feel rejuvenated","Feel renewed","Feel revitalized","Feel stronger","Feel the difference","Feel vibrant","Feel younger","Feel younger instantly","Feel younger now","Feel younger today","Feel your best","Feel your best now","Feel youthful","Feel youthful now","Feeling","Feels","felch","felching","fellatio","Felt","femdom","ferret","ferry","festival","fetische","fetish","fi2ee","Field","Fields","File attached","filez","film","filth","Final","Final call","Final hours","Final notice","Finance","Financial","Financial advice","Financial freedom","Financial independence","Financially independent","Find out how","firearm","firewall","fishing","fisting","Fitness","Fix","Flash sale","flasher","flask","flight","flightsim","flood","fluffer","football","For free","For instant access","For just $","For just $ (amount)","For just $(insert whatever amount)","For just","For just X$","For new customers only","For only","For only XXX amount","For you","Foreclosure","foreplay","Form","fornicate","Free","Free access","Free access/money/gift","Free bonus","Free cell phone","Free consultation","Free download","Free DVD","Free evaluation","Free gift","Free grant money","Free health guide","Free hosting","Free info","Free membership","Free sample","Free shipping","Free shipping offer","Free support","Free Trial","Free!","freebase","freepic","Friend","Friendly reminder","ftpz","fucked","fudgepacker","fukka","Full refund","fury","g4y","Gain","Gain an edge","Gain benefits","Gain confidence","Gain energy","Gain health","Gain muscle","Gain muscle fast","gallery","gamble","gambling","game","GameCube","gaming","ganga","gangbang","gangbangs","ganja","garden","gassing","gay","gayboy","gaylord","Gemini","Genius","genocide","Get","Get access now","Get better fast","Get better results","Get fit","Get fit fast","Get fit quickly","Get healthy","Get healthy fast","Get healthy quick","Get in shape","Get in shape fast","Get in shape instantly","Get in shape now","Get instant access","Get it away","Get it now","Get lean","Get Money","Get more","Get now","Get out of debt","Get out of debt NOW","Get paid","Get results","Get results now","get rich quick","Get rid of","Get ripped","Get slim fast","Get started","get started now","Get strong","Get strong fast","Get strong instantly","Get stronger","Get thin","Get well fast","Get your","Get your money","Get your results","Gift card","Gift certificate","Gift included","gimp","gin","Give it away","Giveaway","Giving away","Giving it away","gizz","gizzum","glider","Glock","goal","gobbler","Gold","golf","gollywog","Good day","Good news","goodwood","gook","gourmet","Grab","gram","Great","Great deal","Great offer","Greetings","Greetings of the day","grenade","gringo","Groundbreaking","growth hormone","Guarantee","Guaranteed","Guaranteed delivery","Guaranteed deposit","Guaranteed income","Guaranteed payment","Guaranteed results","Guaranteed safe","Guaranteed satisfaction","guest","guide","gymnasium","gymnastics","gyppo","h0t","hack","hacker","hackersoftware","hackertool","hackerz","hackology","hackz","hallucinogen","hammered","hammerskin","handicap","hangover","hardcore","hash","hashish","Hassle-free","hate","Have you been turned down?","headhunter","Healing","Health","Health advantage","Health and wellness","Health benefits","Health benefits unlocked","Health boost","Health breakthrough","Health breakthroughs","Health deal","Health discovery","Health enhancement","Health enhancer","Health essentials","Health expert","Health first","Health guarantee","Health hack","Health insider","Health made easy","Health makeover","Health optimizer","Health perks","Health power","Health remedy","Health revolution","Health savings","Health secret","Health secrets revealed","Health shortcut","Health success","Health tips","Health transformation","Health trend","Health upgrade","Healthcare","Healthier","Healthy and happy","heartburn","Hello (with no name included)","Hello!","hemp","hentai","Herbal","Here","hermaphrodite","heroin","heroine","hgh","Hi there","Hidden","Hidden assets","Hidden charges","Hidden costs","Hidden fees","High score","highscore","hike","HIPAA","hire","Hitler","hiv","HMO","hoax","hoaxz","hobby","hockey","hoe","holiday","holocaust","Home","Home based","Home Based business","Home mortgage","Home-based","Home-based business","homo","horny","horoscope","horserace","Hot deal","Hot offer","hotel","hotjob","hottest","Huge discount","Human","Human growth hormone","humidor","humor","humour","hump","hurdles","Hurry","Hurry up","Hurry, while supplies last","hustler","hydroponic","hymie","hyperaesthesia","hyperalgesia","hyperpathia","hypnotic","hypoaesthesia","icewarez","If only it were that easy","illegal","Imagine","Immediate","Immediate access","Immediate action","Immediate benefits","Immediate delivery","Immediate health boost","Immediate health solution","Immediate health upgrade","Immediate improvement","Immediate relief","Immediate results","Immediate results guaranteed","Immediate savings","Immediately","immunization","Important information","Important information regarding","Important notice","Important notification","Improve","Improve fast","Improve health","Improved","Improves","Improving","In accordance with laws","Income","Income from home","Increase","Increase energy","Increase revenue","Increase sales","Increase sales/traffic","Increase stamina","Increase traffic","Increase your chances","Increase your sales","Increased","Increases","Increasing","Incredible","Incredible deal","indoor","infantilism","inflammation","Info you requested","Information you requested","inhalant","Initial investment","inject","injury","innings","innovating","Innovation","innovators","insecure","Insider","Insider tips","Install now","Instant","Instant access","Instant cure","Instant earnings","Instant health benefit","Instant health benefits","Instant health results","Instant health secret","Instant health tips","Instant improvement","Instant income","Instant offers","Instant relief","Instant results","Instant results guaranteed","Instant success","Instant weight loss","Instant wellness","Instantly better","Instantly feel better","Instantly feel great","Instantly healthier","Insurance","Insurance Lose weight","intercourse","Internet market","Internet marketing","interview","intricacies","intricate","Investment","Investment advice","Investment decision","Invoice","iPod","Ireie","island","It's effective","It’s effective","iTunes","jackoff","JACKPOT","javelin","Jaw-dropping","jazz","jerk","jerkoff","Jew","jewelry","Jews","jizz","jizzum","job","Job alert","jobdirect","jobseeker","jobsonline","jobtrak","jockey","Join","Join billions","Join for free","Join millions","Join millions of Americans","Join now","Join thousands","Join Us","joining","joke","journey","Journey ","joy","joypad","joystick","judo","jugs","juicy","jukebox","Junk","karaoke","karate","kayak","keg","ketamine","kidnap","kill","kinky","KKK","klan","kluge","knights","knob","kraut","labia","labor","lacrosse","lager","Lambo","land","landmark","landscape","landscapes","lardass","Laser printer","Last chance","Last Day","Last minute deal","latex","laugh","leader","Leading","league","Leave","Legal","Legal notice","leisure","lesbian","lesbo","lez","liability","Libra","lick","Life","Life insurance","Life-changing","Life-changing results","Life-enhancing","Life-improving","Lifetime","Lifetime access","Lifetime deal","Limited","Limited amount","Limited availability","Limited number","Limited offer","Limited opportunity","Limited supply","limited time","Limited time deal","limited time offer","Limited time only","Limited-time offer","Limited-time only","Limited-time savings","Link","linkz","liplocked","lips","liquor","Live healthier","Loan","Loan approved","Loans","lock","lodging","Long distance phone number","Long distance phone offer","Look amazing","Look and feel better","Look and feel great","Look better now","Look better today","Look fantastic","Look fantastic now","Look great fast","Look younger","Look younger instantly","Look younger now","Lose","Lose belly fat","Lose inches","Lose inches fast","Lose pounds","Lose weight","Lose weight fast","Lose weight instantly","Lose weight spam","Lottery","Low cost","Low costs","Lower interest rate","Lower interest rates","Lower monthly payment","Lower rates","Lower your mortgage rate","lowest","Lowest insurance rates","Lowest interest rate","Lowest price","Lowest price ever","Lowest rate","Lowest rates","LSD","lubricant","lubrication","luck","luggage","lust","Luxury","Luxury car","mace","machete","Magic","Magic pill","magnum","Mail in order form","Main in order form","Maintained","Majestic","Make $","Make money","make money fast","mall","manhood","marihuana","marijuana","Mark this as not junk","Marketing","Marketing solution","Marketing solutions","martini","Mass email","massacre","Mastercard","masterpiece","masturbation","match","Maximize","Medicaid","Medical","Medical breakthrough","Medicare","Medication","Medicine","Medicines","Medigap","Medium","meds","Mega sale","Melt away","Member","Member stuff","Members","Membership","memorabilia","merger","mescaline","Message contains","Message contains disclaimer","Message from","metatarsalgia","meth","methamphetamine","milestone","milestones","militia","Million","Million dollars","Millionaire","Millions","Mind-blowing","minge","Miracle","Miracle pill","Miracles","Miraculous","misuse","MLM","modifier","modify","Moment","Moments","Money","Money 💰","Money back","Money making","Money-back","Money-making","Money-saving","Money-saving tips","Month trial offer","Monthly payment","moped","More Internet Traffic","moron","morphine","Mortgage","Mortgage rates","motel","motherfukka","motorcross","motorsport","movie","mp3","mp5","mpeg","mpeg2vcr","mrn","Multi level marketing","Multi-level marketing","multimedia","multiplayer","murder","Muscle growth","museum","music","n64","NAAWP","naked","Name","Name brand","narcotic","narrates","narrating","narration","narrative","Nascar","nasty","nationjob","Natural","Natural boost","Natural formula","Natural relief","Natural remedy","Natural solution","naughty","nazi","NBA","Near you","necklacing","necrofil","needlework","negro","nekked","netwarez","neuritis","neuropathic","Never","Never again","Never before","New","New customers only","New domain extensions","NFL","NHL","nicotine","Nigerian","nigga","nigger","nightclub","Nintendo","nip","nips","niteclub","nitrous","No age restrictions","No catch","No claim forms","No commitment","No contract","No cost","No credit check","No disappointment","No experience","No extra cost","No fees","No gimmick","No hidden","No hidden charges","No hidden costs","No hidden fees","No hidden сosts","No interest","No interests","No inventory","No investment","No investment required","No medical exams","No middleman","No more","No obligation","No obligation trial","No obligations","No payment required","No prescription needed","No questions asked","No risk","No selling","No side effects","No strings attached","No waiting","No waiting required","No-obligation","No-risk guarantee","No-risk trial","nobwit","Nominated bank account","nookie","nooky","Not intended","Not junk","not just ..... but a ....","not only ... but also...","Not scam","Not shared","Not spam","Notspam","Now","Now only","Now or never","nudity","nuke","Number 1","Number one","nurse","Nutrition","Obligation","occupation","odds","oem","off","Off everything","Off shore","offense","Offer","Offer expires","Offer expires in X days","Offer extended","Offered","Offering","Offers","Offshore","Olympic","On a budget","On sale","Once in a lifetime","Once in a lifetime deal","Once in a lifetime opportunity","Once in lifetime","Once-in-a-lifetime","One hundred percent","One hundred percent free","One hundred percent guaranteed","One time","One time mailing","One-time","Online biz opportunity","Online degree","Online income","Online job","Online marketing","Online pharmacy","Only","Only $","Only a few left","Only for today","opel","Open","Open attachment","Open file","Open this","Open this email!","Opened","openhack","Opening","Opens","opera","opiate","opium","opponent","Opportunities","Opportunity","Opt in","Opt-in","opted","optedin","optedout","optin","optout","oral","Orbitz","orchestra","Order","Order here","Order immediately","Order now","Order shipped by","Order status","Order today","Order yours today","Ordered","Ordering","Orders","Orders shipped by","Orders shipped by shopper","Organic","orgy","ORIF","osteotomy","ounce","outdoors","Outstanding","Outstanding value","Outstanding values","Outstands","overdose","overseas","p1cs","paedophile","paganism","pain","painting","pantomime","panty","parasthesia","party","passport","Password","Passwords","patch","pave","paves","paving","Pay your bills","payout","PCP","pecker","peckerwood","pee","peenis","peepshow","penetrate","penetration","penis","Penis enlargement","Pennies a day","Penny stocks","Per day/per week/per year","Per month","Perfect","Perfect body","Performance","Permanent results","Personal","pervert","peyote","Pharmaceuticals","Pharmacy","Phenomenal","Phone","photograph","photography","phreak","phreaking","phuck","phuk","physical","physician","picpost","pictures","pill","Pills","pimp","pimps","pink","pint","pioneer","pioneering","pipe","Pisces","piss","pissed","pisser","pissing","pitcher","pivotal","plane","Platform","Platforms","playboy","player","playgirl","playmate","Playstation","Please","Please open","Please read","pleasure","poem","poker","polevault","polo","poof","popper","porn","porno","pot","Potent","Potential earnings","powerline","PPO","practitioner","Pre-approved","pregnancy","Prescription","Presently","Prevent","Prevent aging","Prevented","Preventing","Prevents","Preview file","Price","Price protection","Priced","Prices","Pricing","prick","Print form signature","Print from signature","Print out and fax","Priority access","Priority mail","privacy","Private","Privileged","Prize","Prizes","pro","Problem","Problem with shipping","Problem with your order","Produced and sent out","Profit","Profits","progz","Promise","Promise you","Promised","Promises","Promising","protect","Protection","Proven","Proven health tips","Proven results","Proven solution","Proven system","PS2","PSX","psychedelic","pub","pubes","pubic","publisher","puke","punk","Purchase","Purchase now","Pure profit","Pure Profits","Push","pushes","Pushing","pussy","puzzle","pyramid","qualifications","quarterback","queer","Quick","Quick action","Quick and easy","Quick and easy cure","Quick and easy health","Quick and easy results","Quick and easy tips","Quick and effective","Quick and safe","Quick and safe remedy","Quick and safe results","Quick and simple","Quick boost","Quick cure","Quick energy boost","Quick fix","Quick fix solution","Quick healing","Quick health boost","Quick health improvement","Quick health relief","Quick health tips","Quick health transformation","Quick improvement","Quick recovery","Quick recovery tips","Quick relief","Quick remedy","Quick results","Quick results guaranteed","Quick success","Quick transformation","Quick turnaround","Quick upgrade","Quote","Quotes","race","racist","racket","radiation","radiculogram","radio","raft","raghead","rahowa","rail","rally","rammed","ransom","rap","rape","Rapid results","rapids","Rare","Rare opportunity","Rate","Rated","Rates","Rating","Real thing","realaudio","realjukebox","realplayer","Rebate","record","Recover your debt","Recover your debt instantly","recreation","Reduce","Reduce debt","Reduce fat","Reduce stress","Reduced","Reduces","Reducing","reefer","refi","Refinance","Refinance home","Refinanced home","Refund","Regarding","reggae","Rejuvenate","Remarkable","Remarkably","Remarking","Remedy","remote","Removal","Removal instructions","Remove","Remove wrinkles","Removes","Removes wrinkles","Renew","Renew your body","Replica watches","Request","Request now","Request today","Requests","Requires initial investment","Requires investment","reservation","reserve","Reserves the right","resin","resort","respiratory","restaurant","Restore","Restore health","Restores","restricted","Restricted information","Result","Results","Results guaranteed","resume","Reverse","Reverses","Reverses aging","Revitalize","Revolutionary","Revolutionary breakthrough","Revolutionary health","Revolutionize","Revolutionized","Revolutionizes","Revolutionizing","rhyme","riddle","rifle","riot","Risk free","Risk-free","Risk-free trial","Risked","Risking","Risks","rislas","roach","rock","rohypnol","roleplay","Rolex","romantic","room","roulette","Round the world","roundtrip","rowing","rugby","rum","runner","runway","Rush","Rushed","Rushes","Rushing","S 1618","Safe","Safe and effective","Safe and natural","Safe and natural remedy","Safe and secure","Safe formula","safeguard","Safeguard notice","Sagittarius","sail","sailing","sake","Sale","Sales","Sample","samurai","sangria","Satisfaction","Satisfaction guaranteed","Save","Save $","Save $, Save €","Save big","Save big money","Save big month","Save big on health","Save big today","Save instantly","Save money","Save money now","Save more","Save now","Save now on health","Save on health","Save today","Save up to","Save up to 50%","schmack","sciatica","Score","Score with babes","scored","Scorpio","scramble","scratch","screw","scrotum","scuba","scum","Search engine","Search engine listings","Search engine optimisation","Search engines","seaside","season","Secret","Secret tips","Secret to better health","Secret to health","Secrets","Section 301","Secure claim","Secure download","security","seduction","See attachment","See for yourself","See results","seen on","Sega","seks","sekx","Selected","Selected specially","semen","Sensational","Sensitive","Sent in compliance","septic","serialz","Serious","Serious bargain","Serious case","Serious cash","Serious offer","Serious only","Sex","shag","shape","shapes","Shaping","Shed pounds","shit","shite","shithead","shitter","shoot","shop","Shop now","shopper","shopping","Shopping spree","shotgun","Shred","shrooms","sightseeing","Sign up free","Sign up free today","singer","sinus","sixer","skating","skiing","skinhead","slang","sleaze","Slim","Slimming","slit","slots","smartass","smashed","smoke","smoking","snatch","snoring","snorkel","snort","snowboarding","soccer","social","Social security number","society","sodomy","softball","Solution","Soon","Spam","Spam free","spank","special","Special access","Special deal","Special discount","Special discount offer","Special for you","Special gift","Special health alert","Special introductory offer","Special invitation","Special offer","Special price","Special promo","Special promotion","Special rate","Special report","Special savings","Spectacular","speedball","speedway","spend","sperm","spic","spick","spinal","spine","sportsbook","spunk","ssn","stab","stadium","Stainless steel","stake","stamina","Start now","Start saving","Start your journey","Stay healthy","std","steroid","stimulant","Stock alert","Stock disclaimer statement","Stock pick","Stocks/stock pick/stock alert","stoned","stoner","Stop","Stop calling me","Stop emailing me","Stop further distribution","Stop snoring","strangle","Strengthen","stress","striptease","Strong buy","stud","Stuff on sale","Stunning","stupid","Subject to","Subject to cash","Subject to credit","Subject to…","Subjected to","submissive","Subscribe","Subscribe for free","Subscribe now","Success","suck","suicide","Super health tips","Super offer","Super promo","Super savings","Supercharge","Supercharged","Supplement","Supplements","Supplies","Supplies are limited","Supply","supremacy","Supreme","surfing","surgery","Surprise deal","swastika","swim","switchblade","sympathectomy","syringe","tackle","Take action","Take action now","Talks about hidden charges","Talks about prizes","Taurus","taxi","Team","Teen","television","Tells you it's an ad","Tells you it’s an ad","tendinitis","tennis","tent","tequila","Terms","Terms and conditions","terror","terrorist","THC","The best","The best rates","The email asks for a credit card","The following form","theatre","Therapeutics","Therapy","They keep your money – no refund","They keep your Money — no refund!","They try to keep your money no refund","They're just giving it away","This isn't a scam","This isn't junk","This isn't spam","This won't last","This won’t last","Thousands","thumbnailgalleries","thumbnailgallery","tightarse","Time limited","Time-limited","Time-sensitive","Timeshare","Timeshare offers","tip","tipster","tit","tits","To whom it may concern","tobacco","Today","Today only","Today’s deal","Today’s special","toke","tongue","Top benefits","Top deal","Top health benefits","Top health deal","Top health discovery","Top health guide","Top health offer","Top health product","Top health remedy","Top health secret","Top health solution","Top health tip","Top health tips","Top offer","Top performance","Top quality","Top results","Top secret","Top secret remedy","Top seller","Top treatment","Top urgent","Top-notch","Top-rated","Top-rated product","Top-secret formula","topless","torture","tosser","tosspot","Total health makeover","Total satisfaction","Total transformation","Total wellness","touchdown","tourist","tournament","Traffic","train","trainer","trannies","tranny","transexual","transform","Transform your body","Transform your health","Transform your life","transformation","transformative","Transforming","transgender","transvestite","travel","Treat","Treatment","Treatments","Trial","Trial offer","Trial unlimited","trip","tripping","trojan","trophy","Try it now","turnkey","TV","twamp","twat","tweeker","twelver","twink","U.S. dollars","ulcer","ulna","ulnar","Ultimate","Ultimate guide","Ultimate health","Ultimate health guide","Ultimate health solution","Ultimate savings","Ultimate solution","umpire","Unbeatable offer","Unbelievable","uncensored","Uncover the secret","underground","Undisclosed","Undisclosed recipient","undress","unemployed","unhackable","University diplomas","Unlimited","Unlimited trial","unlock","Unlock health","Unlock your potential","unlocked","Unlocking","unlocks","Unmatched","Unparalleled","Unprecedented","unravel","unraveled","unraveling","unravels","Unrivaled","Unsecured credit","Unsecured credit/debt","Unsecured Debt","Unsolicited","Unsubscribe","Unsubscribe here","Unveil","Unveiling","Unveils","Upgrade your health","uppers","Urgent","Urgent response","Urgent response required","US dollars","US dollars / Euros","username","vacancy","Vacation","Vacation offers","vaccination","Vaccine","Valium","Valium Viagra","Vegas","venue","Verified","vertebrae","Viagra","VIAGRA DELIVERY","Vicodin","Video inside","vidz","View attachment","View now","violence","violent","VIP","Viral","virginity","virgins","Virgo","virus","Visa","vision","Visit","Visit our website","Visited","Visiting","Visits","vodka","volleyball","vomit","vulnerability","vulnerable","wager","wank","wanker","wanky","Wants credit card","war","warez","Warranty","Warranty expired","wasted","We hate spam","We honor all","Wealth","Web traffic","webcam","Website visitors","weed","Weekend getaway","Weight control","Weight loss","Weight management","Weight reduction","weight spam","Welcome","Welcomes","welcum","Well-being","Wellness","Wellness solution","Wellness tips","whank","What are you waiting for?","What's keeping you?","While available","While in stock","While stocks last","While you sleep","whiskey","whisky","whitepower","whitey","whities","Who really wins?","whore","Why pay more?","Will not believe your eyes","Win","Win big","winamp","wine","Winner","Winning","winspin","wog","Won","Wonder drug","Wonderful","Wonderfully","wop","worm","WPWW","wrestling","Xbox","XTC","xxx","yacht","YID","You have been chosen","You have been selected","You qualify","You said:","You will not believe your eyes","You won","You’re a winner!","You're a winner! Won","You've been selected","Your chance","Your income","Your status","Your success","yourmp3","youthful","Youthful appearance","Zero chance","Zero percent","Zero risk","zog","zoofilia","zoophilia","zundel"
]

def get_highlighted_text(text, spam_list):
    # Regex to wrap spam words with <mark> for highlight
    for word in spam_list:
        pattern = re.compile(rf"(?i)\b({re.escape(word)})\b")
        text = pattern.sub(r"<mark>\1</mark>", text)
    return text

def get_leftover_spam_words(text, spam_words):
    leftover_words = []
    for word in spam_words:
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            leftover_words.append(word)
    return leftover_words

# --- Configuration for LLM ---
os.environ["LITELLM_DEBUG"] = "False" # Set to False for production, True for debugging
OPENROUTER_API_KEY = "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" # Replace with your actual key
OPENROUTER_MODEL_NAME = "openrouter/google/gemini-2.5-flash-preview-05-20"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

# Define a custom LLM class that wraps litellm.completion
class CustomLiteLLM(BaseLLM):
    model: str = OPENROUTER_MODEL_NAME
    api_key: str = OPENROUTER_API_KEY
    base_url: str = OPENROUTER_API_BASE
    temperature: float = 0.7

    @property
    def _llm_type(self) -> str:
        return "custom_litellm"

    def _generate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> LLMResult:
        generations = []
        for prompt in prompts:
            messages = [{"role": "user", "content": prompt}]
            try:
                response = completion(
                    model=self.model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    messages=messages,
                    temperature=self.temperature,
                    custom_llm_provider="openrouter",
                    caching=False # Bypass caching
                )
                
                # Log OPENROUTER_REQUEST_ID if debug is enabled
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"OpenRouter Request ID: {response.id}")

                content = response.choices[0].message.content
                generations.append([{"text": content}])
            except Exception as e:
                raise ValueError(f"Error in CustomLiteLLM _generate call: {e}")
        return LLMResult(generations=generations)

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        return {
            "model": self.model,
            "api_key_set": bool(self.api_key),
            "base_url": self.base_url,
            "temperature": self.temperature,
        }

# Instantiate the custom LLM
openrouter_llm = CustomLiteLLM()

# Load environment variables
load_dotenv()

# --- Database Functions ---
# --- Database Functions ---
DATABASE_NAME = 'journal_data.db'
DB_DIR = os.path.dirname(os.path.abspath(__file__))  # Always relative to this file

import mysql.connector # Add this import at the top of the file

def get_db_connection(db_name: str = "sqlite"):
    if db_name == "sqlite":
        db_path = os.path.join(DB_DIR, DATABASE_NAME)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Allows accessing columns by name
        return conn
    elif db_name == "mysql":
        return mysql.connector.connect(
            host=os.getenv("DRAFTS_DB_HOST"),
            user=os.getenv("DRAFTS_DB_USER"),
            password=os.getenv("DRAFTS_DB_PASS"),
            database=os.getenv("DRAFTS_DB_NAME")
        )

_DB = Path(__file__).parent / "interspire_analysis_results.db"

def _connect():
    return sqlite3.connect(_DB)


def fetch_journals():
    conn = get_db_connection() # Use SQLite connection
    journals = conn.execute('SELECT * FROM journal_details').fetchall()
    conn.close()
    return journals


def fetch_domains():
    conn = get_db_connection() # Use SQLite connection
    domains = conn.execute('SELECT * FROM domains').fetchall()
    conn.close()
    return domains

def fetch_cfp_templates():
    conn = get_db_connection() # Use SQLite connection
    templates = conn.execute('SELECT content FROM cfp_templates').fetchall()
    conn.close()
    return [t['content'] for t in templates]

def fetch_open_templates():
    conn = get_db_connection() # Use SQLite connection
    templates = conn.execute('SELECT content FROM open_templates').fetchall()
    conn.close()
    return [t['content'] for t in templates]

# Function to calculate core word count
def calculate_core_word_count(draft_text: str) -> int:
    lines = draft_text.strip().split('\n')
    
    # Find start of content (after salutation)
    content_start_index = 0
    found_salutation = False
    for i, line in enumerate(lines):
        if line.startswith("Subject: "):
            continue
        elif not found_salutation and line.strip() != "": # This is the salutation line
            found_salutation = True
            content_start_index = i + 1
            break
        elif line.strip() == "" and not found_salutation: # Skip blank lines before salutation
            continue
        elif not found_salutation: # If no salutation, content starts after subjects
            content_start_index = i
            break
    
    # Find end of content (before signature)
    content_end_index = len(lines)
    for i, line in enumerate(lines):
        if "Warm Regards," in line:
            content_end_index = i
            break
            
    core_content_lines = lines[content_start_index:content_end_index]
    
    word_count = 0
    for line in core_content_lines:
        if line.strip() != "": # Exclude blank lines
            word_count += len(line.split())
            
    return word_count

def extract_core_content(draft_text: str) -> str:
    lines = draft_text.strip().split('\n')
    
    content_start_index = 0
    # Find start of content (after subject lines and salutation)
    found_salutation = False
    for i, line in enumerate(lines):
        if line.startswith("Subject: "):
            continue
        elif not found_salutation and line.strip() != "": # This is the salutation line
            found_salutation = True
            content_start_index = i + 1
            break
        elif line.strip() == "" and not found_salutation: # Skip blank lines before salutation
            continue
        elif not found_salutation: # If no salutation, content starts after subjects
            content_start_index = i
            break
    
    # Find end of content (before signature)
    content_end_index = len(lines)
    for i, line in enumerate(lines):
        if "Warm Regards," in line:
            content_end_index = i
            break
            
    core_content_lines = lines[content_start_index:content_end_index]
    return "\n".join(core_content_lines).strip()

def parse_crew(out) -> dict:
    """
    Return the JSON dict produced by a CrewAI run.
    If the agent prints extra text or duplicates the JSON block,
    grab the *first* valid JSON object we can find.
    """
    # 1) normalise to a raw string
    raw = (
        out.strip()
        if isinstance(out, str)
        else (getattr(out, "raw", "") or "").strip()
    )

    # strip code fences
    raw = re.sub(r"```(?:json)?|```", "", raw, flags=re.I).strip()

    # 2) try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 3) fallback → extract first balanced {...}
    start = raw.find("{")
    if start == -1:
        return {"error": "No JSON found", "raw_output": raw}

    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                snippet = raw[start : i + 1]
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    break

    return {"error": "Invalid JSON", "raw_output": raw}


def filter_agent_output(output_text: str, include_subjects: bool = False) -> tuple[list[str], str]:
    lines = output_text.strip().split('\n')
    subject_lines = []
    filtered_body_lines = []

    for line in lines:
        if line.startswith("Subject: ") and include_subjects:
            subject_lines.append(line.replace("Subject: ", "").strip())
        elif not (line.startswith("Thought:") or
                  line.startswith("I will") or
                  line.startswith("Here's my plan:") or
                  line.startswith("Let's ") or
                  line.startswith("Analyze the spam word list") or # New filter
                  line.startswith("Go through the draft") or # New filter
                  line.startswith("For each instance of a spam word") or # New filter
                  line.startswith("Choose a synonym") or # New filter
                  line.startswith("Replace the spam word") or # New filter
                  line.startswith("Ensure formatting") or # New filter
                  line.startswith("Do a final review") or # New filter
                  line.startswith("Example replacements") or # New filter
                  line.startswith("Brainstorm inventive layout elements") or # New filter
                  line.startswith("Improve introduction") or # New filter
                  line.startswith("Reframe sections") or # New filter
                  line.startswith("Highlight key data") or # New filter
                  line.startswith("Refine language") or # New filter
                  line.startswith("Structure the prompt") or # New filter
                  line.startswith("Ensure every original data is present") or # New filter
                  line.startswith("Apply formatting rules") or # New filter
                  line.startswith("Review for engagement and aesthetics") or # New filter
                  line.startswith("Introduction:") or # New filter
                  line.startswith("Introduction of IJN:") or # New filter
                  line.startswith("Mission & Scope:") or # New filter
                  line.startswith("Why Publish:") or # New filter
                  line.startswith("Submission Process:") or # New filter
                  line.startswith("Prompt to undertaking:") or # New filter
                  line.startswith("Closing:") or # New filter
                  line.startswith("Signature:") or # New filter
                  line.startswith("Drafting approach:") # New filter
                  ):
            filtered_body_lines.append(line)
            
    return subject_lines, "\n".join(filtered_body_lines).strip()

def get_recent_email_analysis(journal_name: str, limit: int = 10) -> list[dict]:
    """Return the last `limit` campaign rows for the journal, newest-first."""
    try:
        with get_conn() as conn: # Use get_conn from db.py
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT overall_score, subject_overall_score,
                           structure_score, email_content_score
                    FROM interspire_analysis_results
                    WHERE journal_name = %s
                    ORDER BY sent_at DESC
                    LIMIT %s
                    """,
                    (journal_name, limit),
                )
                columns = [c[0] for c in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching recent email analysis: {e}")
        return []

def get_last_waiver_percentage(journal_name: str) -> Optional[int]:
    """Return last granted waiver % from interspire_data (or None)."""
    try:
        with get_conn() as conn: # Use get_conn from db.py
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT waiver_percentage
                    FROM interspire_data
                    WHERE journal_name = %s
                      AND waiver_percentage IS NOT NULL
                    ORDER BY sent_at DESC
                    LIMIT 1
                    """,
                    (journal_name,),
                )
                row = cur.fetchone()
                return row[0] if row else None
    except Exception as e:
        logger.error(f"Error fetching last waiver percentage: {e}")
        return None

def recommend_waiver(level: str, last: Optional[int]) -> Tuple[int, str]:
    mapping = {"⚠️ Targeted": 15, "✅ Aggressive": 35}
    if level == "❌ Minimal":
        if last is not None:
            return 0, f"No waiver is recommended (last time {last}% was granted)."
        return 0, "Tier-3 journal with minimal waiver stance; waiver not advised."

    # Targeted or Aggressive
    rec = mapping.get(level, 0)
    if last is not None:
        return rec, f"Last waiver {last}% — suggest {rec}% now."
    return rec, f"No previous waiver; suggest {rec}% this time."
