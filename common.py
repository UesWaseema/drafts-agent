import os
import sqlite3 # Re-add sqlite3 import
import re
import json
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Any, Mapping, Optional, Tuple
from db import get_conn # Import get_conn from the new db.py
from langchain_core.language_models.llms import BaseLLM
from langchain_core.outputs import LLMResult
from litellm import completion
from pydantic import Field           # ← ADD THIS LINE


# Placeholder for spam words. User will add them manually.
# These should be in lowercase for case-insensitive matching.
SPAM_WORDS = [
"100%","100 more please","100% effective","100% off","22mag","40oz","50% off","a better you","abduct","aboard","abuse","acceptance","access","access attachment","access file","access here","access now","access right away","accommodation","accordingly","accounts","accumulator","achieve goals","acid","acquisition","act","act fast","act immediately","act now","act now!","act right now","action","action required","activate link","acts","ad","addict","additional income","addresses","addresses on cd","adult","advanced health","advanced solution","adventure","aerobic","affordable","affordable deal","age gracefully","age-defying","agency","aintree","airfare","airhead","airline","airplane","airport","ak47","album","ale","algorithm","alkaloid","all","all natural","all natural/new","all new","all-natural","all-new","allodynia","allowance","allowed","alter","amazed","amazing","amazing benefits","amazing deal","amazing health offer","amazing improvement","amazing offer","amazing savings","amazing stuff","ammo","amphetamine","amuse","anaesthesia","anal","analgesia","analgesic","anarchy","angeldust","anonymous","ante","antique","antiviral","antivirus","anul","anus","anxiety","apartment","applicant","apply here","apply now","apply now!","apply online","appointment","apprenticeship","appz","aquarium","aquarius","archery","archive","archivecrack","arena","aries","armed","aroused","arrival","arse","arseface","arsehole","arthrodesis","arthroplasty","arthroscopy","artillery","aryan","as","as seen on","as seen on oprah","ass","asshole","assmaster","assreamer","asswipe","asthma","astounding","astrology","astronomy","at no cost","athlete","athletics","attached document","attachment","attack","attention","atv","auto email removal","avoid","avoid bankruptcy","avoiding","avoids","award","awarding","awards","b1g","babe","babes","bacardi","baccarat","backdoor","backpack","baggage","ballet","band","barbecue","barbeque","barbie","barbiturate","barf","bargain","baseball","basketball","bastard","battery","bbq","bdsm","be amazed","be healthy","be slimmer","be surprised","be your own boss","beach","beacon","beaner","beastiality","beat","become a member","beer","before it's too late","being a member","believe me","beneficial","beneficial offer","beneficiary","benefit","benefits","benefitted","benefitting","best","best bargain","best choice","best deal","best deal in town","best health","best health advice","best health deal","best health discovery","best health offer","best health practices","best health results","best health solution","best health strategies","best health tips","best mortgage rates","best offer","best offer ever","best price","best prices","best quality","best rates","best results","best solution","best value","best-kept health secret","best-kept secret","best-selling","bestiality","bet","better health","better health solutions","better health today","better than","better than ever","betting","beverage","bicycle","big bucks","big savings","biggest savings","bigot","bike","billion","bingo","bitch","bitchslap","blackbox","blackjack","blacks","blade","blockbuster","blonde","bloody","blow","blowout","blunt","body fat","body transformation","bomb","bondage","boner","bong","bonghit","bonus","bonus gift","boobs","booked","bookies","bookmaker","boost","boost health fast","boost metabolism","boost your","boost your immunity","boost your life","booty","booze","bosom","boss","boundaries","boundary","bourbon","boutique","bowl","bowling","boxing","brand new pager","brawl","breakthrough","breakthroughs","breathtaking","brewsky","broadway","brothel","brotherhood","browse","bsdm","budweiser","bug","bugger","build","build muscle","building","builds","bukkake","bulk","bulk purchase","bullshit","bureau","burn calories","burn fat","bust","busty","but not limited to","butt","butts","buy","buy direct","buy now","buy today","buying judgements","buying judgments","buyout","buzzed","bypass","cabaret","cabin","cable converter","calcar","call","call free","call free/now","call me","call now","call now!","call toll-free","calling creditors","calls","camp","campground","camping","cams","can we have a minute of your time?","can you help us?","can't live without","cancel","cancel at any time","cancel now","cancellation","cancellation required","candidate","cannabis","cannot be combined","cannot be combined with any other offer","canoe","capricorn","captain","caravan","card accepted","cards accepted","careerbuilder","careercity","careerweb","cash","cash bonus","cash cash cash","cash out","cash-out","cashback","catch","causalgia","cavity","celeb","celebration","certified","certified experts","certifies","certify","certifying","chalet","challenge","challenged","challenges","challenging","chance","chances","chapter","charter","chatgpt","chatgpt said:","cheap","cheap meds","check","check or money order","checkout","chick","chicks","chinaman","chink","chiva","choke","cholesterol","cialis","cinema","circulatory","claim","claim now","claim your discount","claim your discount now!","claim your prize","claims","claims to be legal","classic","classical","clearance","cleavage","click","click below","click here","click me to download","click now","click this link","click to get","click to open","click to remove","click to view","clinic","clinical trial","clit","clits","closing soon","clown","club","coach","coast","cocaine","cock","cocks","cocksucker","code","codeine","codez","coding","collaborating","collaboration","collect","collect child support","collection","colt","comedy","comminuted","compare","compare now","compare online","compare rates","compete for your business","competition","complimentary","concert","condom","confidential","confidential deal","confidential proposal","confidentiality","confidentiality on all orders","confidentially on all orders","congratulations","console","consolidate","consolidate debt","consolidate debt and credit","consolidate your debt","constipation","contact us immediately","content marketing","coors","copayment","copy accurately","copy dvds","cornerstone","cornerstones","corona","cost","costs","cottaging","countdown","coupon","covid","cpm","crack","cracked","cracker","crackz","craft","crank","craps","crash","creampie","credit","credit bureaus","credit card","credit card offers","credit or debit","crotch","cruise","cum","cunnilingus","cunt","cunts","cure","cures","currency","customs","cutting-edge","cyberattack","cybercrime","cybersecurity","cycle","dagger","dago","dance","darkie","darky","darts","dci","dea1","dea1s","dea1z","deadline","deal","deal breaker","deal ending soon","debt","debug","decode","decrypt","deductible","defeat","defense","dego","denervation","denied","dental","descrambler","detect","detox","devil","diabetic","diarrhea","dick","dickhead","dicks","diet","diet pill","dig up dirt on friends","digital","digital marketing","dike","dildo","dimebag","direct email","direct marketing","disable","disco","discotheque","discount","discount offer","discover","discover ","discovered","discoveries","discovering","discovers","discovery","discus","dj","do it now","do it today","dock","doctor","doctor-approved","doctor-recommended","doctor's advice","doctor’s secret","document","doggystyle","dogmatist","dollars","domination","don’t delay","don't delete","don't hesitate","don’t hesitate!","don't miss","don’t miss","don’t miss out","don’t miss your chance","don’t wait","don't waste time","dong","dope","dormant","double your","double your cash","double your income","double your leads","double your wealth","downers","downline","download attachment","download now","downloadable content","downloadz","drastically reduced","dreamcast","drugs","drunk","dss","dssware","dumb","dumbass","dyke","dynamite","dysaesthesia","dysfunction","earn","easy health","easy money","easy solution","easy steps","ecstacy","ecstasy","education","effective","effective treatment","eightball","eligible","eliminate","email extractor","email harvest","email marketing","embark","empower","empowered","empowering","empowers","emulator","enable","encode","encrypt","end pain","endocrine","ends tonight","energize","enhance","enhance performance","enhance your life","enhancement","enlargo","enrollee","enthusiast","eob","epidural","equestrian","erase","erase wrinkles","erectile","erection","erotic","erotik","euphoria","euphoric","evite","examination","excite","excites","exciting","exciting opportunity","exclusive","exclusive access","exclusive benefit","exclusive benefits","exclusive bonus","exclusive deal","exclusive discounts","exclusive health access","exclusive health discovery","exclusive health guide","exclusive health insights","exclusive health offer","exclusive health report","exclusive health secrets","exclusive health tips","exclusive info","exclusive insight","exclusive insights","exclusive invitation","exclusive offer","exclusive opportunity","exclusive promotion","exclusive rate","exclusive rewards","exclusive sale","exclusive savings","exclusive solution","exclusive trial","excrete","excretion","excursion","exhibition","expedia","expert advice","expert recommendation","expert-approved","expire","expired","expires","expires today","expiring","expiring soon","explode","explode your business","explore","explored","explores","exploring","explosion","exterminate","extra","extra cash","extra income","extra savings","extract email","extraordinary","extremist","f r e e","facesit","fag","faggot","famous","fanfics","fans","fantasies","fantastic","fantastic deal","fantastic offer","fantasy","fast","fast acting","fast acting cure","fast acting remedy","fast acting solution","fast and easy","fast and natural","fast approval","fast cash","fast health boost","fast health tips","fast relief","fast results","fast results guaranteed","fast results now","fast solution","fast viagra delivery","fat burner","fat burning","fat loss","fat loss solution","fat melting","feel","feel amazing","feel amazing fast","feel amazing instantly","feel amazing now","feel amazing today","feel better","feel better fast","feel better immediately","feel better now","feel better today","feel confident","feel confident now","feel energized","feel energized instantly","feel energized now","feel fantastic","feel fantastic now","feel fantastic today","feel great","feel great instantly","feel great now","feel great today","feel incredible","feel more confident","feel refreshed","feel refreshed instantly","feel rejuvenated","feel renewed","feel revitalized","feel stronger","feel the difference","feel vibrant","feel younger","feel younger instantly","feel younger now","feel younger today","feel your best","feel your best now","feel youthful","feel youthful now","feeling","feels","felch","felching","fellatio","felt","femdom","ferret","ferry","festival","fetische","fetish","fi2ee","field","fields","file attached","filez","film","filth","final","final call","final hours","final notice","finance","financial","financial advice","financial freedom","financial independence","financially independent","find out how","firearm","firewall","fishing","fisting","fitness","fix","flash sale","flasher","flask","flight","flightsim","flood","fluffer","football","for free","for instant access","for just $","for just $ (amount)","for just $(insert whatever amount)","for just","for just x$","for new customers only","for only","for only xxx amount","for you","foreclosure","foreplay","form","fornicate","free","free access","free access/money/gift","free bonus","free cell phone","free consultation","free download","free dvd","free evaluation","free gift","free grant money","free health guide","free hosting","free info","free membership","free sample","free shipping","free shipping offer","free support","free trial","free!","freebase","freepic","friend","friendly reminder","ftpz","fucked","fudgepacker","fukka","full refund","fury","g4y","gain","gain an edge","gain benefits","gain confidence","gain energy","gain health","gain muscle","gain muscle fast","gallery","gamble","gambling","game","gamecube","gaming","ganga","gangbang","gangbangs","ganja","garden","gassing","gay","gayboy","gaylord","gemini","genius","genocide","get","get access now","get better fast","get better results","get fit","get fit fast","get fit quickly","get healthy","get healthy fast","get healthy quick","get in shape","get in shape fast","get in shape instantly","get in shape now","get instant access","get it away","get it now","get lean","get money","get more","get now","get out of debt","get out of debt now","get paid","get results","get results now","get rich quick","get rid of","get ripped","get slim fast","get started","get started now","get strong","get strong fast","get strong instantly","get stronger","get thin","get well fast","get your","get your money","get your results","gift card","gift certificate","gift included","gimp","gin","give it away","giveaway","giving away","giving it away","gizz","gizzum","glider","glock","goal","gobbler","gold","golf","gollywog","good day","good news","goodwood","gook","gourmet","grab","gram","great","great deal","great offer","greetings","greetings of the day","grenade","gringo","groundbreaking","growth hormone","guarantee","guaranteed","guaranteed delivery","guaranteed deposit","guaranteed income","guaranteed payment","guaranteed results","guaranteed safe","guaranteed satisfaction","guest","guide","gymnasium","gymnastics","gyppo","h0t","hack","hacker","hackersoftware","hackertool","hackerz","hackology","hackz","hallucinogen","hammered","hammerskin","handicap","hangover","hardcore","hash","hashish","hassle-free","hate","have you been turned down?","headhunter","healing","health advantage","health and wellness","health benefits","health benefits unlocked","health boost","health breakthrough","health breakthroughs","health deal","health discovery","health enhancement","health enhancer","health essentials","health expert","health first","health guarantee","health hack","health insider","health made easy","health makeover","health optimizer","health perks","health power","health remedy","health revolution","health savings","health secret","health secrets revealed","health shortcut","health success","health tips","health transformation","health trend","health upgrade","healthier","healthy and happy","heartburn","hello (with no name included)","hello!","hemp","hentai","herbal","here","hermaphrodite","heroin","heroine","hgh","hi there","hidden","hidden assets","hidden charges","hidden costs","hidden fees","high score","highscore","hike","hipaa","hire","hitler","hmo","hoax","hoaxz","hobby","hockey","hoe","holiday","holocaust","home","home based","home based business","home mortgage","home-based","home-based business","homo","horny","horoscope","horserace","hot deal","hot offer","hotel","hotjob","hottest","huge discount","human growth hormone","humidor","humor","humour","hump","hurdles","hurry","hurry up","hurry, while supplies last","hustler","hydroponic","hymie","hyperaesthesia","hyperalgesia","hyperpathia","hypnotic","hypoaesthesia","icewarez","if only it were that easy","illegal","imagine","immediate","immediate access","immediate action","immediate benefits","immediate delivery","immediate health boost","immediate health solution","immediate health upgrade","immediate improvement","immediate relief","immediate results","immediate results guaranteed","immediate savings","immediately","important information","important information regarding","important notice","important notification","improve","improve fast","improve health","improved","improves","improving","in accordance with laws","income","income from home","increase","increase energy","increase revenue","increase sales","increase sales/traffic","increase stamina","increase traffic","increase your chances","increase your sales","increased","increases","increasing","incredible","incredible deal","indoor","infantilism","info you requested","information you requested","inhalant","initial investment","inject","injury","innings","innovating","innovation","innovators","insecure","insider","insider tips","install now","instant","instant access","instant cure","instant earnings","instant health benefit","instant health benefits","instant health results","instant health secret","instant health tips","instant improvement","instant income","instant offers","instant relief","instant results","instant results guaranteed","instant success","instant weight loss","instant wellness","instantly better","instantly feel better","instantly feel great","instantly healthier","insurance","insurance lose weight","intercourse","internet market","internet marketing","interview","intricacies","intricate","investment","investment advice","investment decision","invoice","ipod","ireie","island","it's effective","it’s effective","itunes","jackoff","jackpot","javelin","jaw-dropping","jazz","jerk","jerkoff","jew","jewelry","jews","jizz","jizzum","job","job alert","jobdirect","jobseeker","jobsonline","jobtrak","jockey","join","join billions","join for free","join millions","join millions of americans","join now","join thousands","join us","joining","joke","journey","journey ","joy","joypad","joystick","judo","jugs","juicy","jukebox","junk","karaoke","karate","kayak","keg","ketamine","kidnap","kill","kinky","kkk","klan","kluge","knights","knob","kraut","labia","labor","lacrosse","lager","lambo","land","landmark","landscape","landscapes","lardass","laser printer","last chance","last day","last minute deal","latex","laugh","leader","leading","league","leave","legal","legal notice","leisure","lesbian","lesbo","lez","liability","libra","lick","life","life insurance","life-changing","life-changing results","life-enhancing","life-improving","lifetime","lifetime access","lifetime deal","limited","limited amount","limited availability","limited number","limited offer","limited opportunity","limited supply","limited time","limited time deal","limited time offer","limited time only","limited-time offer","limited-time only","limited-time savings","link","linkz","liplocked","lips","liquor","live healthier","loan","loan approved","loans","lock","lodging","long distance phone number","long distance phone offer","look amazing","look and feel better","look and feel great","look better now","look better today","look fantastic","look fantastic now","look great fast","look younger","look younger instantly","look younger now","look younger today","lose","lose belly fat","lose inches","lose inches fast","lose pounds","lose weight","lose weight fast","lose weight instantly","lose weight spam","lottery","low cost","low costs","lower interest rate","lower interest rates","lower monthly payment","lower rates","lower your mortgage rate","lowest","lowest insurance rates","lowest interest rate","lowest price","lowest price ever","lowest rate","lowest rates","lsd","lubricant","lubrication","luck","luggage","lust","luxury","luxury car","mace","machete","magic","magic pill","magnum","mail in order form","main in order form","maintained","majestic","make $","make money","make money fast","mall","manhood","marihuana","marijuana","mark this as not junk","marketing","marketing solution","marketing solutions","martini","mass email","massacre","mastercard","masterpiece","masturbation","match","maximize","medicaid","medical breakthrough","medicare","medication","medigap","medium","meds","mega sale","melt away","member","member stuff","members","membership","memorabilia","merger","mescaline","message contains","message contains disclaimer","message from","metatarsalgia","meth","methamphetamine","milestone","milestones","militia","million","million dollars","millionaire","millions","mind-blowing","minge","miracle","miracle pill","miracles","miraculous","misuse","mlm","modifier","modify","moment","moments","money","money 💰","money back","money making","money-back","money-making","money-saving","money-saving tips","month trial offer","monthly payment","moped","more internet traffic","moron","morphine","mortgage","mortgage rates","motel","motherfukka","motorcross","motorsport","movie","mp3","mp5","mpeg","mpeg2vcr","mrn","multi level marketing","multi-level marketing","multimedia","multiplayer","murder","muscle growth","museum","music","n64","naawp","naked","name","name brand","narcotic","narrates","narrating","narration","narrative","nascar","nasty","nationjob","natural","natural boost","natural formula","natural relief","natural remedy","natural solution","naughty","nazi","nba","near you","necklacing","necrofil","needlework","negro","nekked","netwarez","neuritis","neuropathic","never","never again","never before","new customers only","new domain extensions","nfl","nhl","nicotine","nigerian","nigga","nigger","nightclub","nintendo","nip","nips","niteclub","nitrous","no age restrictions","no catch","no claim forms","no commitment","no contract","no cost","no credit check","no disappointment","no experience","no extra cost","no fees","no gimmick","no hidden","no hidden charges","no hidden costs","no hidden fees","no hidden сosts","no interest","no interests","no inventory","no investment","no investment required","no medical exams","no middleman","no more","no obligation","no obligation trial","no obligations","no payment required","no prescription needed","no questions asked","no risk","no selling","no side effects","no strings attached","no waiting","no waiting required","no-obligation","no-risk guarantee","no-risk trial","nobwit","nominated bank account","nookie","nooky","not intended","not junk","not just ..... but a ....","not only ... but also...","not scam","not shared","not spam","notspam","now","now only","now or never","nudity","nuke","number 1","number one","nurse","obligation","occupation","odds","oem","off","off everything","off shore","offense","offer","offer expires","offer expires in x days","offer extended","offered","offering","offers","offshore","olympic","on a budget","on sale","once in a lifetime","once in a lifetime deal","once in a lifetime opportunity","once in lifetime","once-in-a-lifetime","one hundred percent","one hundred percent free","one hundred percent guaranteed","one time","one time mailing","one-time","online biz opportunity","online degree","online income","online job","online marketing","online pharmacy","only","only $","only a few left","only for today","opel","open","open attachment","open file","open this","open this email!","opened","openhack","opening","opens","opera","opiate","opium","opponent","opportunities","opportunity","opt in","opt-in","opted","optedin","optedout","optin","optout","orbitz","orchestra","order","order here","order immediately","order now","order shipped by","order status","order today","order yours today","ordered","ordering","orders","orders shipped by","orders shipped by shopper","organic","orgy","orif","osteotomy","ounce","outdoors","outstanding","outstanding value","outstanding values","outstands","overdose","overseas","p1cs","paedophile","paganism","painting","pantomime","panty","parasthesia","party","passport","password","passwords","patch","pave","paves","paving","pay your bills","payout","pcp","pecker","peckerwood","pee","peenis","peepshow","penetrate","penetration","penis","penis enlargement","pennies a day","penny stocks","per day/per week/per year","per month","perfect","perfect body","performance","permanent results","personal","pervert","peyote","pharmaceuticals","pharmacy","phenomenal","phone","photograph","photography","phreak","phreaking","phuck","phuk","physical","physician","picpost","pictures","pill","pills","pimp","pimps","pink","pint","pioneer","pioneering","pipe","pisces","piss","pissed","pisser","pissing","pitcher","pivotal","plane","platform","platforms","playboy","player","playgirl","playmate","playstation","please","please open","please read","pleasure","poem","poker","polevault","polo","poof","popper","porn","porno","pot","potent","potential earnings","powerline","ppo","practitioner","pre-approved","pregnancy","prescription","presently","prevent","prevent aging","prevented","preventing","prevents","preview file","price","price protection","priced","prices","pricing","prick","print form signature","print from signature","print out and fax","priority access","priority mail","privacy","private","privileged","prize","prizes","pro","problem","problem with shipping","problem with your order","produced and sent out","profit","profits","progz","promise","promise you","promised","promises","promising","protect","protection","proven","proven health tips","proven results","proven solution","proven system","ps2","psx","psychedelic","pub","pubes","pubic","publisher","puke","punk","purchase","purchase now","pure profit","pure profits","push","pushes","pushing","pussy","puzzle","pyramid","qualifications","quarterback","queer","quick","quick action","quick and easy","quick and easy cure","quick and easy health","quick and easy results","quick and effective","quick and safe","quick and safe remedy","quick and safe results","quick and simple","quick boost","quick cure","quick energy boost","quick fix","quick fix solution","quick healing","quick health boost","quick health improvement","quick health relief","quick health tips","quick health transformation","quick improvement","quick recovery","quick recovery tips","quick relief","quick remedy","quick results","quick results guaranteed","quick success","quick transformation","quick turnaround","quick upgrade","quote","quotes","race","racist","racket","radiculogram","radio","raft","raghead","rahowa","rail","rally","rammed","ransom","rap","rape","rapid results","rapids","rare","rare opportunity","rate","rated","rates","rating","real thing","realaudio","realjukebox","realplayer","rebate","record","recover your debt","recover your debt instantly","recreation","reduce","reduce debt","reduce fat","reduce stress","reduced","reduces","reducing","reefer","refi","refinance","refinance home","refinanced home","refund","regarding","reggae","rejuvenate","remarkable","remarkably","remarking","remedy","remote","removal","removal instructions","remove","remove wrinkles","removes","removes wrinkles","renew","renew your body","replica watches","request","request now","request today","requests","requires initial investment","requires investment","reservation","reserve","reserves the right","resin","resort","restaurant","restore","restore health","restores","restricted","restricted information","result","results guaranteed","resume","reverse","reverses","reverses aging","revitalize","revolutionary","revolutionary breakthrough","revolutionary health","revolutionize","revolutionized","revolutionizes","revolutionizing","rhyme","riddle","rifle","riot","risk free","risk-free","risk-free trial","risked","risking","risks","rislas","roach","rock","rohypnol","roleplay","rolex","romantic","room","roulette","round the world","roundtrip","rowing","rugby","rum","runner","runway","rush","rushed","rushes","rushing","s 1618","safe","safe and effective","safe and natural","safe and natural remedy","safe and secure","safe formula","safeguard","safeguard notice","sagittarius","sail","sailing","sake","sale","sales","sample","samurai","sangria","satisfaction","satisfaction guaranteed","save","save $","save $, save €","save big","save big money","save big month","save big on health","save big today","save instantly","save money","save money now","save more","save now","save now on health","save on health","save today","save up to","save up to 50%","schmack","sciatica","score","score with babes","scored","scorpio","scramble","scratch","screw","scrotum","scuba","scum","search engine","search engine listings","search engine optimisation","search engines","seaside","season","secret","secret tips","secret to better health","secret to health","secrets","section 301","secure claim","secure download","security","seduction","see attachment","see for yourself","seen on","sega","seks","sekx","selected","selected specially","semen","sensational","sensitive","sent in compliance","septic","serialz","serious","serious bargain","serious case","serious cash","serious offer","serious only","sex","shag","shape","shapes","shaping","shed pounds","shit","shite","shithead","shitter","shoot","shop","shop now","shopper","shopping","shopping spree","shotgun","shred","shrooms","sightseeing","sign up free","sign up free today","singer","sinus","sixer","skating","skiing","skinhead","slang","sleaze","slim","slimming","slit","slots","smartass","smashed","smoke","smoking","snatch","snoring","snorkel","snort","snowboarding","soccer","social","social security number","society","sodomy","softball","solution","soon","spam","spam free","spank","special","special access","special deal","special discount","special discount offer","special for you","special gift","special health alert","special introductory offer","special invitation","special offer","special price","special promo","special promotion","special rate","special report","special savings","spectacular","speedball","speedway","spend","sperm","spic","spick","sportsbook","spunk","ssn","stab","stadium","stainless steel","stake","stamina","start now","start saving","start your journey","stay healthy","std","steroid","stimulant","stock alert","stock disclaimer statement","stock pick","stocks/stock pick/stock alert","stoned","stoner","stop","stop calling me","stop emailing me","stop further distribution","stop snoring","strangle","strengthen","stress","striptease","strong buy","stud","stuff on sale","stunning","stupid","subject to","subject to cash","subject to credit","subject to…","subjected to","submissive","subscribe","subscribe for free","subscribe now","success","suck","suicide","super health tips","super offer","super promo","super savings","supercharge","supercharged","supplement","supplements","supplies","supplies are limited","supply","supremacy","supreme","surfing","surprise deal","swastika","swim","switchblade","sympathectomy","syringe","tackle","take action","take action now","talks about hidden charges","talks about prizes","taurus","taxi","team","teen","television","tells you it's an ad","tells you it’s an ad","tendinitis","tennis","tent","tequila","terms","terms and conditions","terror","terrorist","thc","the best","the best rates","the email asks for a credit card","the following form","theatre","therapeutics","they keep your money – no refund","they keep your money — no refund!","they try to keep your money no refund","they're just giving it away","this isn't a scam","this isn't junk","this isn't spam","this won't last","this won’t last","thousands","thumbnailgalleries","thumbnailgallery","tightarse","time limited","time-limited","time-sensitive","timeshare","timeshare offers","tip","tipster","tit","tits","to whom it may concern","tobacco","today","today only","today’s deal","today’s special","toke","tongue","top benefits","top deal","top health benefits","top health deal","top health discovery","top health guide","top health offer","top health product","top health remedy","top health secret","top health solution","top health tip","top health tips","top offer","top performance","top quality","top results","top secret","top secret remedy","top seller","top treatment","top urgent","top-notch","top-rated","top-rated product","top-secret formula","topless","torture","tosser","tosspot","total health makeover","total satisfaction","total transformation","total wellness","touchdown","tourist","tournament","traffic","train","trainer","trannies","tranny","transexual","transform","transform your body","transform your health","transform your life","transformation","transformative","transforming","transgender","transvestite","travel","treat","trial","trial offer","trial unlimited","trip","tripping","trojan","trophy","try it now","turnkey","tv","twamp","twat","tweeker","twelver","twink","u.s. dollars","ulcer","ulna","ulnar","ultimate","ultimate guide","ultimate health","ultimate health guide","ultimate health solution","ultimate savings","ultimate solution","umpire","unbeatable offer","unbelievable","uncensored","uncover the secret","underground","undisclosed","undisclosed recipient","undress","unemployed","unhackable","university diplomas","unlimited","unlimited trial","unlock","unlock health","unlock your potential","unlocked","unlocking","unlocks","unmatched","unparalleled","unprecedented","unravel","unraveled","unraveling","unravels","unrivaled","unsecured credit","unsecured credit/debt","unsecured debt","unsolicited","unsubscribe","unsubscribe here","unveil","unveiling","unveils","upgrade your health","uppers","urgent","urgent response","urgent response required","us dollars","us dollars / euros","username","vacancy","vacation","vacation offers","vaccination","vaccine","valium","valium viagra","vegas","venue","verified","vertebrae","viagra","viagra delivery","vicodin","video inside","vidz","view attachment","view now","violence","violent","vip","viral","virginity","virgins","virgo","virus","visa","vision","visit","visit our website","visited","visiting","visits","vodka","volleyball","vomit","vulnerability","vulnerable","wager","wank","wanker","wanky","wants credit card","war","warez","warranty","warranty expired","wasted","we hate spam","we honor all","wealth","web traffic","webcam","website visitors","weed","weekend getaway","weight control","weight loss","weight management","weight reduction","weight spam","welcome","welcomes","welcum","well-being","wellness","wellness solution","wellness tips","whank","what are you waiting for?","what's keeping you?","while available","while in stock","while stocks last","while you sleep","whiskey","whisky","whitepower","whitey","whities","who really wins?","whore","why pay more?","will not believe your eyes","win","win big","winamp","wine","winner","winning","winspin","wog","won","wonder drug","wonderful","wonderfully","wop","worm","wpww","wrestling","xbox","xtc","xxx","yacht","yid","you have been chosen","you have been selected","you qualify","you said:","you will not believe your eyes","you won","you’re a winner!","you're a winner! won","you've been selected","your chance","your income","your status","your success","yourmp3","youthful","youthful appearance","zero chance","zero percent","zero risk","zog","zoofilia","zoophilia","zundel"
]

def get_highlighted_text(text, spam_list):
    # Regex to wrap spam words with <mark> for highlight
    for word in spam_list:
        pattern = re.compile(rf"(?i)\b({re.escape(word)})\b")
        text = pattern.sub(r"<mark>\1</mark>", text)
    return text

def get_leftover_spam_words(text: str, bad_words: list[str]) -> list[str]:
    """
    Return **unique** spam words in *text*, case-insensitive.
    """
    badset = {w.lower() for w in bad_words}
    words  = re.findall(r"\b\w+\b", text, flags=re.I)     # ← ignore-case
    return sorted({w for w in words if w.lower() in badset})


SALUTATION_RX = re.compile(r"^.*?[,:\-]\s*", re.I | re.S)  # up to first “Dear …,” line
CLOSING_RX    = re.compile(r"\bwarm regards\b", re.I)

def _slice_core_email(text: str) -> str:
    """
    Return everything AFTER the salutation placeholder
    and BEFORE 'Warm regards'.
    """
    # Strip first salutation block
    after_sal = SALUTATION_RX.sub("", text, count=1)

    # Cut at 'Warm regards'
    match = CLOSING_RX.search(after_sal)
    if match:
        after_sal = after_sal[:match.start()]

    return after_sal.strip()

def calc_spam_metrics(email_txt: str) -> dict:
    """
    → { words: int, spam_words: int, pct: float, spam_list: list[str], score: int }
    """
    core = _slice_core_email(email_txt)
    words = re.findall(r"\b\w+\b", core)
    word_count = len(words)

    spam_hits = [w for w in words if w.lower() in SPAM_WORDS]
    spam_count = len(spam_hits)
    pct = (spam_count / word_count * 100) if word_count else 0.0

    # map % → 1-5
    if   pct <= 1:  points = 5
    elif pct <= 2:  points = 4
    elif pct <= 3:  points = 3
    elif pct <= 5:  points = 2
    else:           points = 1

    return dict(
        words        = word_count,
        spam_words   = spam_count,
        pct          = round(pct, 2),
        spam_list    = spam_hits,
        score        = points
    )

INTERSPIRE_DOMAINS = {"CFP10", "CFP12", "CFP9", "CFP4", "CFP2"}
MAILWIZZ_DOMAINS   = {"NCFP9", "NCFP10", "NCFP11", "NCFP12"}

# --- Configuration for LLM ---
os.environ["LITELLM_DEBUG"] = "False" # Set to False for production, True for debugging
# Load the OpenRouter key from the shell environment
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")  # make sure this is exported

if not OPENROUTER_API_KEY:
    raise RuntimeError(
        "OPENROUTER_API_KEY environment variable is not set. "
        "Export it before running the script."
    )
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

class CustomLiteLLM(BaseLLM):
    model: str                               # ← declare it
    temperature: float = 0.7
    api_key: str = Field(default=OPENROUTER_API_KEY)
    base_url: str = Field(default=OPENROUTER_API_BASE)

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
                    caching=False, # Bypass caching
                    extra_body={ "mode": "thinking", "budget": 150000 }
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

def get_model_name(llm) -> str:
    return getattr(llm, "model", llm._identifying_params.get("model", "unknown"))

# --- Waiver-stance routing --------------------------------------------------
STANCE_MODEL_MAP: dict[str, tuple[str, float]] = {
    "minimal":   ("openrouter/google/gemini-2.5-pro-preview-05-06", 0.7),
    "targeted":  ("openrouter/anthropic/claude-sonnet-4",     0.32),
    "aggressive":("openrouter/openai/gpt-4.1-2025-04-14",     0.25),
}

def _clean_stance(raw: str) -> str:
    """
    Strip emoji / symbols and whitespace, then lowercase.
    Examples:
        "❌ Minimal"   -> "minimal"
        "⚠️ Targeted"  -> "targeted"
        "✅ Aggressive"-> "aggressive"
    """
    words = raw.split()          # splits on any whitespace
    return words[-1].lower()     # grab last word, e.g. "Minimal"

def get_llm_for_stance(waiver_stance: str) -> CustomLiteLLM:
    key = _clean_stance(waiver_stance)
    model, temp = STANCE_MODEL_MAP[key]
    return CustomLiteLLM(model=model, temperature=temp)


gpt4o_llm = CustomLiteLLM(               # mini GPT-4o used by HTML agent
    model="openrouter/openai/gpt-4o-mini-2024-07-18",
    temperature=0.0,
)

gpt4o_full_llm = CustomLiteLLM(             # Full-size GPT-4o released 2024-08-06, deterministic (T=0.0)
    model="openrouter/openai/gpt-4o-2024-08-06",
    temperature=0.0,
)

# Full-size Gemini 2.5 preview via OpenRouter
gemini25_preview_llm = CustomLiteLLM(       # released 2024-05-06 preview
    model="openrouter/google/gemini-2.5-pro-preview-05-06",
    temperature=0.7,                       # ⬅️  higher T for synonym variety
)

# Load environment variables
load_dotenv()

import os
import sqlite3

# --- Database Functions ---
DATABASE_NAME = 'journal_data.db'
DB_DIR = os.path.dirname(os.path.abspath(__file__))  # Always relative to this file

def get_db_connection():
    db_path = os.path.join(DB_DIR, DATABASE_NAME)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

def fetch_journals():
    conn = get_db_connection()
    journals = conn.execute('SELECT * FROM journal_details').fetchall()
    conn.close()
    return journals


def fetch_domains():
    conn = get_db_connection()
    domains = conn.execute('SELECT * FROM domains').fetchall()
    conn.close()
    return domains

def fetch_cfp_templates():
    conn = get_db_connection()
    templates = conn.execute('SELECT content FROM cfp_templates').fetchall()
    conn.close()
    return [t['content'] for t in templates]

def fetch_open_templates():
    conn = get_db_connection()
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

def filter_agent_output(output_text: str, include_subjects: bool = False) -> tuple[list[str], str]:
    lines = output_text.strip().split('\n')
    subject_lines = []
    filtered_body_lines = []

    for line in lines:
        if line.startswith("Subject: ") and include_subjects:
            subject_lines.append(line.replace("Subject: ", "").strip())
        elif not (
                  line.startswith("Thought:") or
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
    """Return the last limit campaign rows for the journal, newest-first."""
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
