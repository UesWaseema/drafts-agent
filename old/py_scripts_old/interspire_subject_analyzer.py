import re
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class InterspireSubjectAnalyzer:
    """
    Analyzes Interspire email subject lines based on predefined rules to score and rank
    new email drafts. This class implements validated rules from historical analysis
    to identify top-quartile campaigns.
    """

    def __init__(self, historical_data=None):
        """
        Initializes the InterspireSubjectAnalyzer with optional historical Interspire
        campaign data.

        Args:
            historical_data (pd.DataFrame, optional): A Pandas DataFrame containing
                                                       historical email campaign data.
                                                       Defaults to None.
        """
        self.historical_data = historical_data
        self.spam_trigger_words = [
            "free", "money", "urgent", "sex", "viagra", "casino", "loan", "guarantee",
            "winner", "congratulations", "discount", "offer", "deal", "save", "cash",
            "earn", "investment", "income", "opportunity", "work from home", "online",
            "marketing", "seo", "mlm", "get paid", "extra income", "fast cash",
            "no obligation", "risk-free", "satisfaction guaranteed", "collect",
            "refinance", "mortgage", "pre-approved", "hidden", "secret", "revealed",
            "shocking", "unbelievable", "don't miss", "special", "selected for you",
            "alert", "warning", "security", "verify", "account", "password", "login",
            "update", "confirm", "transaction", "invoice", "bill", "payment", "order",
            "shipment", "delivery", "tracking", "refund", "claim", "suspicious",
            "unusual activity", "compromised", "fraud", "scam", "virus", "malware",
            "phishing", "spam", "junk", "bulk", "undisclosed", "confidential", "private",
            "personal", "sensitive", "secret", "classified", "urgent attention", "immediate action",
            "respond now", "reply", "forward", "share", "tell a friend", "please read",
            "important", "critical", "mandatory", "required", "action required", "attention",
            "as seen on", "featured", "endorsed", "certified", "approved", "official",
            "authentic", "genuine", "real", "true", "verified", "legitimate", "trusted",
            "reputable", "reliable", "proven", "effective", "powerful", "ultimate",
            "best", "top", "leading", "premier", "elite", "premium", "superior",
            "advanced", "cutting-edge", "state-of-the-art", "revolutionary", "breakthrough",
            "new", "introducing", "announcing", "just released", "fresh", "hot", "popular",
            "trending", "viral", "buzz", "hype", "exciting", "incredible", "amazing",
            "fantastic", "wonderful", "super", "great", "awesome", "cool", "nice",
            "good", "fine", "okay", "alright", "sure", "yes", "no", "maybe", "perhaps",
            "can", "will", "should", "must", "might", "could", "would", "may", "shall",
            "is", "are", "am", "was", "were", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "done", "doing", "go", "goes", "went", "gone", "going",
            "come", "comes", "came", "coming", "get", "gets", "got", "getting", "make",
            "makes", "made", "making", "see", "sees", "saw", "seen", "seeing", "take",
            "takes", "took", "taken", "taking", "know", "knows", "knew", "known", "knowing",
            "think", "thinks", "thought", "thinking", "want", "wants", "wanted", "wanting",
            "use", "uses", "used", "using", "find", "finds", "found", "finding", "give",
            "gives", "gave", "given", "giving", "tell", "tells", "told", "telling", "ask",
            "asks", "asked", "asking", "work", "works", "worked", "working", "seem",
            "seems", "seemed", "seeming", "feel", "feels", "felt", "feeling", "try",
            "tries", "tried", "trying", "leave", "leaves", "left", "leaving", "call",
            "calls", "called", "calling", "need", "needs", "needed", "needing", "mean",
            "means", "meant", "meaning", "keep", "keeps", "kept", "keeping", "let",
            "lets", "letting", "begin", "begins", "began", "begun", "beginning", "help",
            "helps", "helped", "helping", "talk", "talks", "talked", "talking", "start",
            "starts", "started", "starting", "run", "runs", "ran", "running", "show",
            "shows", "showed", "shown", "showing", "hear", "hears", "heard", "hearing",
            "play", "plays", "played", "playing", "move", "moves", "moved", "moving",
            "like", "likes", "liked", "liking", "live", "lives", "lived", "living",
            "believe", "believes", "believed", "believing", "hold", "holds", "held",
            "holding", "bring", "brings", "brought", "bringing", "happen", "happens",
            "happened", "happening", "write", "writes", "wrote", "written", "writing",
            "provide", "provides", "provided", "providing", "sit", "sits", "sat", "sitting",
            "stand", "stands", "stood", "standing", "lose", "loses", "lost", "losing",
            "pay", "pays", "paid", "paying", "meet", "meets", "met", "meeting", "include",
            "includes", "included", "including", "continue", "continues", "continued",
            "continuing", "set", "sets", "setting", "learn", "learns", "learned", "learning",
            "change", "changes", "changed", "changing", "lead", "leads", "led", "leading",
            "understand", "understands", "understood", "understanding", "watch", "watches",
            "watched", "watching", "follow", "follows", "followed", "following", "stop",
            "stops", "stopped", "stopping", "create", "creates", "created", "creating",
            "speak", "speaks", "spoke", "spoken", "speaking", "read", "reads", "read",
            "reading", "allow", "allows", "allowed", "allowing", "add", "adds", "added",
            "adding", "spend", "spends", "spent", "spending", "grow", "grows", "grew",
            "grown", "growing", "open", "opens", "opened", "opening", "walk", "walks",
            "walked", "walking", "win", "wins", "won", "winning", "offer", "offers",
            "offered", "offering", "remember", "remembers", "remembered", "remembering",
            "love", "loves", "loved", "loving", "consider", "considers", "considered",
            "considering", "appear", "appears", "appeared", "appearing", "buy", "buys",
            "bought", "buying", "wait", "waits", "waited", "waiting", "serve", "serves",
            "served", "serving", "die", "dies", "died", "dying", "send", "sends", "sent",
            "sending", "build", "builds", "built", "building", "stay", "stays", "stayed",
            "staying", "fall", "falls", "fell", "fallen", "falling", "cut", "cuts",
            "cutting", "reach", "reaches", "reached", "reaching", "kill", "kills",
            "killed", "killing", "raise", "raises", "raised", "raising", "pass", "passes",
            "passed", "passing", "sell", "sells", "sold", "selling", "decide", "decides",
            "decided", "deciding", "return", "returns", "returned", "returning", "explain",
            "explains", "explained", "explaining", "hope", "hopes", "hoped", "hoping",
            "develop", "develops", "developed", "developing", "carry", "carries",
            "carried", "carrying", "break", "breaks", "broke", "broken", "breaking",
            "receive", "receives", "received", "receiving", "agree", "agrees", "agreed",
            "agreeing", "support", "supports", "supported", "supporting", "hit", "hits",
            "hitting", "produce", "produces", "produced", "producing", "eat", "eats",
            "ate", "eaten", "eating", "cover", "covers", "covered", "covering", "catch",
            "catches", "caught", "catching", "draw", "draws", "drew", "drawn", "drawing",
            "choose", "chooses", "chose", "chosen", "choosing", "cause", "causes",
            "caused", "causing", "require", "requires", "required", "requiring", "report",
            "reports", "reported", "reporting", "drive", "drives", "drove", "driven",
            "driving", "represent", "represents", "represented", "representing", "pull",
            "pulls", "pulled", "pulling", "prepare", "prepares", "prepared", "preparing",
            "discuss", "discusses", "discussed", "discussing", "prove", "proves",
            "proved", "proven", "proving", "teach", "teaches", "taught", "teaching",
            "touch", "touches", "touched", "touching", "remove", "removes", "removed",
            "removing", "close", "closes", "closed", "closing", "enter", "enters",
            "entered", "entering", "present", "presents", "presented", "presenting",
            "prepare", "prepares", "prepared", "preparing", "discuss", "discusses",
            "discussed", "discussing", "prove", "proves", "proved", "proven", "proving",
            "teach", "teaches", "taught", "teaching", "touch", "touches", "touched",
            "touching", "remove", "removes", "removed", "removing", "close", "closes",
            "closed", "closing", "enter", "enters", "entered", "entering", "present",
            "presents", "presented", "presenting", "depend", "depends", "depended",
            "depending", "enable", "enables", "enabled", "enabling", "additionally",
            "furthermore", "moreover", "however", "therefore", "consequently", "thus",
            "hence", "accordingly", "otherwise", "instead", "rather", "nevertheless",
            "nonetheless", "notwithstanding", "although", "though", "even though",
            "whereas", "while", "whilst", "unless", "until", "since", "because", "as",
            "for", "so", "that", "in order that", "so that", "such that", "provided that",
            "assuming that", "given that", "if", "only if", "whether", "or not", "and",
            "but", "or", "nor", "yet", "so", "for", "either", "neither", "both", "not only",
            "but also", "as well as", "in addition to", "apart from", "aside from",
            "except for", "instead of", "in place of", "on behalf of", "by means of",
            "in spite of", "despite", "because of", "due to", "owing to", "thanks to",
            "on account of", "as a result of", "in consequence of", "for the sake of",
            "with a view to", "in order to", "so as to", "as far as", "as long as",
            "as much as", "as soon as", "as well as", "no sooner than", "hardly when",
            "scarcely when", "barely when", "where", "wherever", "when", "whenever",
            "while", "whilst", "as", "before", "after", "until", "till", "since", "by the time",
            "once", "as soon as", "the moment", "the minute", "the second", "the instant",
            "the very moment", "the very minute", "the very second", "the very instant",
            "now that", "given that", "granted that", "assuming that", "provided that",
            "providing that", "on condition that", "in case", "in the event that",
            "lest", "for fear that", "so that", "in order that", "to the end that",
            "with the result that", "with the effect that", "so...that", "such...that",
            "too...to", "enough...to", "what", "whatever", "who", "whoever", "whom",
            "whomever", "whose", "which", "whichever", "how", "however", "why", "whereby",
            "whence", "wherefore", "whereupon", "wherewith", "whereinto", "wherefrom",
            "whereout", "whereover", "whereunder", "whereunto", "whereupon", "wherewithal"
        ]

    def analyze_subject_length(self, subject_line):
        """
        Analyzes the length of the subject line and provides a performance score and recommendations.

        Rules:
        - Score +30 points for 35-55 characters
        - Score -25 points for <30 or >60 characters
        - Identify optimal range of 50-60 chars (peak performance zone)

        Args:
            subject_line (str): The email subject line to analyze.

        Returns:
            dict: A dictionary containing character count, optimal range status, performance score,
                  and a recommendation.
        """
        char_count = len(subject_line)
        performance_score = 0.0
        optimal_range = False
        recommendation = ""

        if 35 <= char_count <= 55:
            performance_score += 30
            recommendation = "Subject line length is within the optimal range (35-55 characters)."
        elif char_count < 30:
            performance_score -= 25
            recommendation = "Subject line is too short (<30 characters). Consider making it more descriptive."
        elif char_count > 60:
            performance_score -= 25
            recommendation = "Subject line is too long (>60 characters). Consider shortening it for better readability."
        else:
            recommendation = "Subject line length is acceptable, but not in the primary optimal range."

        if 50 <= char_count <= 60:
            optimal_range = True
            if not recommendation: # Only add if no other recommendation was made
                recommendation = "Subject line is in the peak performance zone (50-60 characters)."
            else: # Append to existing recommendation if it's not empty
                recommendation += " Also, it's in the peak performance zone (50-60 characters)."

        return {
            'character_count': char_count,
            'optimal_range': optimal_range,
            'performance_score': performance_score,
            'recommendation': recommendation.strip()
        }
    
    def analyze_caps_ratio(self, subject_line):
        """
        Analyzes the capitalization ratio of the subject line and provides performance impact
        and warnings.

        Rules:
        - Calculate exact percentage of capital letters
        - Optimal range: 10-20% (performance boost zone)
        - Warning threshold: >30% (bounce risk increases 13x)
        - Penalty calculation for excessive caps

        Args:
            subject_line (str): The email subject line to analyze.

        Returns:
            dict: A dictionary containing caps percentage, performance impact, bounce risk,
                  and a recommendation.
        """
        total_chars = len(subject_line)
        if total_chars == 0:
            return {
                'caps_percentage': 0.0,
                'performance_impact': "N/A",
                'bounce_risk': "N/A",
                'recommendation': "Subject line is empty, cannot analyze capitalization."
            }

        capital_chars = sum(1 for char in subject_line if char.isupper())
        caps_percentage = (capital_chars / total_chars) * 100

        performance_impact = "Neutral"
        bounce_risk = "Low"
        recommendation = ""

        if 10 <= caps_percentage <= 20:
            performance_impact = "Positive (Performance Boost Zone)"
            recommendation = "Capitalization is within the optimal 10-20% range."
        elif caps_percentage > 30:
            performance_impact = "Negative (High Bounce Risk)"
            bounce_risk = "High (increases bounces 13x)"
            recommendation = "Excessive capitalization (>30%) detected. This significantly increases bounce risk."
        elif caps_percentage < 10:
            performance_impact = "Neutral to Slightly Negative"
            recommendation = "Capitalization is below 10%. Consider increasing capitalization slightly for better performance."
        else:
            performance_impact = "Acceptable"
            recommendation = "Capitalization is acceptable, but not in the optimal range."

        return {
            'caps_percentage': round(caps_percentage, 2),
            'performance_impact': performance_impact,
            'bounce_risk': bounce_risk,
            'recommendation': recommendation
        }
    
    def detect_spam_patterns(self, subject_line):
        """
        Detects common spam patterns in the subject line.

        Rules:
        - ALL-CAPS words detection
        - Excessive punctuation patterns
        - Common spam trigger words
        - Domain mismatch indicators (not applicable for subject line analysis alone,
          will be noted as a limitation or handled externally if context allows)

        Args:
            subject_line (str): The email subject line to analyze.

        Returns:
            dict: A dictionary containing spam risk score, specific patterns found, and severity.
        """
        spam_risk_score = 0.0
        patterns_found = []
        severity = "Low"

        # 1. ALL-CAPS words detection
        all_caps_words = re.findall(r'\b[A-Z]{2,}\b', subject_line)
        if all_caps_words:
            patterns_found.append(f"ALL-CAPS words: {', '.join(all_caps_words)}")
            spam_risk_score += len(all_caps_words) * 5 # Each all-caps word adds to risk
            if len(all_caps_words) > 2:
                severity = "Medium"

        # 2. Excessive punctuation patterns (e.g., !!!, ???, !?!)
        excessive_punctuation_matches = re.findall(r'([!?.])\1+', subject_line)
        if excessive_punctuation_matches:
            patterns_found.append(f"Excessive punctuation: {', '.join(set(excessive_punctuation_matches))}")
            spam_risk_score += len(excessive_punctuation_matches) * 10 # Each instance adds to risk
            severity = "High"

        # 3. Common spam trigger words
        subject_lower = subject_line.lower()
        found_spam_words = [word for word in self.spam_trigger_words if word in subject_lower]
        if found_spam_words:
            patterns_found.append(f"Spam trigger words: {', '.join(set(found_spam_words))}")
            spam_risk_score += len(found_spam_words) * 3 # Each spam word adds to risk
            if spam_risk_score > 15:
                severity = "High"
            elif spam_risk_score > 5:
                severity = "Medium"

        # Determine overall severity
        if spam_risk_score > 20:
            severity = "Critical"
        elif spam_risk_score > 10:
            severity = "High"
        elif spam_risk_score > 0:
            severity = "Medium"
        else:
            severity = "Low"

        return {
            'risk_score': round(spam_risk_score, 2),
            'patterns_found': patterns_found,
            'severity': severity
        }
    
    def extract_keyword_performance(self, subject_line):
        """
        Extracts beneficial keywords and estimates their performance boost.

        Rules:
        - Detect "call for papers" variations
        - Calculate click-through boost (+0.008)
        - Identify other high-performing keywords from historical data (placeholder for now)

        Args:
            subject_line (str): The email subject line to analyze.

        Returns:
            dict: A dictionary containing a list of beneficial keywords found and
                  an estimated performance boost.
        """
        beneficial_keywords = []
        estimated_boost = 0.0
        subject_lower = subject_line.lower()

        # Detect "call for papers" variations
        if re.search(r'call for papers', subject_lower):
            beneficial_keywords.append("call for papers")
            estimated_boost += 0.008 # Lifts clicks +0.008

        # Placeholder for other high-performing keywords from historical data
        # In a real scenario, this would involve looking up keywords in self.historical_data
        # For example:
        # if self.historical_data is not None:
        #     for index, row in self.historical_data.iterrows():
        #         if "some_other_keyword" in subject_lower and row['keyword'] == "some_other_keyword":
        #             beneficial_keywords.append("some_other_keyword")
        #             estimated_boost += row['average_click_through_boost'] # Example

        return {
            'beneficial_keywords': beneficial_keywords,
            'estimated_boost': round(estimated_boost, 3)
        }
    
    def validate_punctuation(self, subject_line):
        """
        Validates punctuation usage in the subject line.

        Rules:
        - Punctuation limits: <= 1 exclamation or question mark

        Args:
            subject_line (str): The email subject line to analyze.

        Returns:
            dict: A dictionary containing punctuation count, compliance status, and recommendations.
        """
        exclamation_count = subject_line.count('!')
        question_mark_count = subject_line.count('?')
        total_punctuation = exclamation_count + question_mark_count

        compliance_status = True
        recommendations = []

        if total_punctuation > 1:
            compliance_status = False
            recommendations.append("Limit exclamation and question marks to 1 or less for better performance.")

        return {
            'punctuation_count': total_punctuation,
            'compliance_status': compliance_status,
            'recommendations': recommendations
        }
    
    def calculate_subject_effectiveness(self, subject_line):
        """
        Calculates a composite effectiveness score for the subject line based on all rules.

        Args:
            subject_line (str): The email subject line to analyze.

        Returns:
            float: A composite effectiveness score between 0 and 100.
        """
        # Initialize a base score
        effectiveness_score = 50.0 # Start with a neutral score

        # Get results from individual analysis methods
        length_analysis = self.analyze_subject_length(subject_line)
        caps_analysis = self.analyze_caps_ratio(subject_line)
        spam_detection = self.detect_spam_patterns(subject_line)
        keyword_performance = self.extract_keyword_performance(subject_line)
        punctuation_validation = self.validate_punctuation(subject_line)

        # Apply scoring based on rules
        # Length Analysis
        effectiveness_score += length_analysis['performance_score']

        # Capitalization Analysis
        if caps_analysis['performance_impact'] == "Positive (Performance Boost Zone)":
            effectiveness_score += 15 # Significant boost for optimal caps
        elif caps_analysis['performance_impact'] == "Negative (High Bounce Risk)":
            effectiveness_score -= 20 # Significant penalty for excessive caps
        elif caps_analysis['performance_impact'] == "Neutral to Slightly Negative":
            effectiveness_score -= 5 # Small penalty for low caps

        # Spam Pattern Detection
        # Higher spam risk means lower effectiveness
        effectiveness_score -= spam_detection['risk_score'] * 0.5 # Scale down spam risk impact

        # Keyword Boost
        effectiveness_score += keyword_performance['estimated_boost'] * 1000 # Scale up boost for score

        # Punctuation Limits
        if not punctuation_validation['compliance_status']:
            effectiveness_score -= 10 # Penalty for non-compliance

        # Ensure score is within 0-100 range
        effectiveness_score = max(0, min(100, effectiveness_score))

        return round(effectiveness_score, 2)
    
    def generate_subject_feedback(self, subject_line):
        """
        Generates a list of actionable recommendations based on the subject line analysis.

        Args:
            subject_line (str): The email subject line to analyze.

        Returns:
            list: A list of strings, each representing an actionable recommendation.
        """
        feedback = []

        length_analysis = self.analyze_subject_length(subject_line)
        if length_analysis['recommendation']:
            feedback.append(f"Length: {length_analysis['recommendation']}")

        caps_analysis = self.analyze_caps_ratio(subject_line)
        if caps_analysis['recommendation']:
            feedback.append(f"Capitalization: {caps_analysis['recommendation']}")

        spam_detection = self.detect_spam_patterns(subject_line)
        if spam_detection['patterns_found']:
            feedback.append(f"Spam Risk: Detected patterns - {'; '.join(spam_detection['patterns_found'])}. Severity: {spam_detection['severity']}.")

        keyword_performance = self.extract_keyword_performance(subject_line)
        if keyword_performance['beneficial_keywords']:
            feedback.append(f"Keywords: Found beneficial keywords: {', '.join(keyword_performance['beneficial_keywords'])}. Estimated boost: {keyword_performance['estimated_boost']}.")

        punctuation_validation = self.validate_punctuation(subject_line)
        if punctuation_validation['recommendations']:
            feedback.extend([f"Punctuation: {rec}" for rec in punctuation_validation['recommendations']])

        if not feedback:
            feedback.append("Subject line looks good! No specific recommendations at this time.")

        return feedback
    
    def validate_against_rules(self, subject_line):
        """
        Validates the subject line against all defined rules and provides a comprehensive report.

        Args:
            subject_line (str): The email subject line to validate.

        Returns:
            dict: A dictionary containing a rule compliance report and an overall pass/fail status.
        """
        rule_compliance_report = {}
        overall_pass = True

        # Length Analysis
        length_analysis = self.analyze_subject_length(subject_line)
        rule_compliance_report['length_compliance'] = {
            'status': "Pass" if 35 <= length_analysis['character_count'] <= 55 else "Fail",
            'details': length_analysis['recommendation']
        }
        if not (35 <= length_analysis['character_count'] <= 55):
            overall_pass = False

        # Capitalization Analysis
        caps_analysis = self.analyze_caps_ratio(subject_line)
        caps_status = "Pass"
        if caps_analysis['caps_percentage'] < 10 or caps_analysis['caps_percentage'] > 20:
            caps_status = "Fail"
            overall_pass = False
        if caps_analysis['caps_percentage'] > 30: # More severe failure for high bounce risk
            caps_status = "Critical Fail"
            overall_pass = False
        rule_compliance_report['caps_compliance'] = {
            'status': caps_status,
            'details': caps_analysis['recommendation']
        }

        # Spam Pattern Detection
        spam_detection = self.detect_spam_patterns(subject_line)
        spam_status = "Pass"
        if spam_detection['severity'] in ["Medium", "High", "Critical"]:
            spam_status = "Fail"
            overall_pass = False
        rule_compliance_report['spam_compliance'] = {
            'status': spam_status,
            'details': f"Risk Score: {spam_detection['risk_score']}, Patterns: {'; '.join(spam_detection['patterns_found']) if spam_detection['patterns_found'] else 'None'}, Severity: {spam_detection['severity']}"
        }

        # Keyword Performance (considered for effectiveness, not strict compliance pass/fail)
        keyword_performance = self.extract_keyword_performance(subject_line)
        rule_compliance_report['keyword_impact'] = {
            'status': "N/A (Impact on effectiveness)",
            'details': f"Beneficial Keywords: {', '.join(keyword_performance['beneficial_keywords']) if keyword_performance['beneficial_keywords'] else 'None'}, Estimated Boost: {keyword_performance['estimated_boost']}"
        }

        # Punctuation Validation
        punctuation_validation = self.validate_punctuation(subject_line)
        punctuation_status = "Pass"
        if not punctuation_validation['compliance_status']:
            punctuation_status = "Fail"
            overall_pass = False
        rule_compliance_report['punctuation_compliance'] = {
            'status': punctuation_status,
            'details': f"Total '!' or '?': {punctuation_validation['punctuation_count']}. Recommendations: {'; '.join(punctuation_validation['recommendations']) if punctuation_validation['recommendations'] else 'None'}"
        }

        return {
            'rule_compliance_report': rule_compliance_report,
            'overall_pass': overall_pass
        }

if __name__ == "__main__":
    # Example Usage
    analyzer = InterspireSubjectAnalyzer()

    test_subjects = [
        "Unlock Your FREE Prize Now!!!", # Spammy, too long, excessive caps
        "Important Update: Your Account Security", # Good length, neutral caps
        "Call for Papers: Submit Your Research Today!", # Keyword, good length, good caps
        "hello", # Too short
        "THIS IS A TEST SUBJECT LINE WITH ALL CAPS AND TOO MANY EXCLAMATION MARKS!!!!", # Very spammy
        "A short subject", # Too short
        "Discover the secrets to financial freedom and earn passive income!", # Spam words
        "Webinar: Boost Your Sales with AI-Powered Marketing Strategies", # Good
        "Limited Time Offer! Get 50% OFF All Products Now!", # Spam words, excessive caps
        "Your exclusive invitation to our annual conference" # Good
    ]

    for i, subject in enumerate(test_subjects):
        print(f"\n--- Analyzing Subject {i+1}: '{subject}' ---")
        
        # Analyze individual aspects
        length_info = analyzer.analyze_subject_length(subject)
        print(f"Length Analysis: {length_info}")

        caps_info = analyzer.analyze_caps_ratio(subject)
        print(f"Caps Analysis: {caps_info}")

        spam_info = analyzer.detect_spam_patterns(subject)
        print(f"Spam Detection: {spam_info}")

        keyword_info = analyzer.extract_keyword_performance(subject)
        print(f"Keyword Performance: {keyword_info}")

        punctuation_info = analyzer.validate_punctuation(subject)
        print(f"Punctuation Validation: {punctuation_info}")

        # Calculate overall effectiveness
        effectiveness_score = analyzer.calculate_subject_effectiveness(subject)
        print(f"Overall Effectiveness Score: {effectiveness_score}/100")

        # Get actionable feedback
        feedback = analyzer.generate_subject_feedback(subject)
        print("Actionable Feedback:")
        for item in feedback:
            print(f"- {item}")
            
        # Get compliance report
        compliance_report = analyzer.validate_against_rules(subject)
        print(f"Overall Compliance: {'PASS' if compliance_report['overall_pass'] else 'FAIL'}")
        print("Detailed Compliance Report:")
        for rule, report in compliance_report['rule_compliance_report'].items():
            print(f"  {rule}: Status - {report['status']}, Details - {report['details']}")

    # Performance Validation (Placeholder - requires historical data with known top-quartile campaigns)
    # To validate 81% accuracy, you would need a dataset with 'subject_line' and a 'is_top_quartile' flag.
    # Then, you would run calculate_subject_effectiveness on all subjects, sort them, and check
    # if the top 25% of your ranked subjects indeed match 81% of the known top-quartquartile campaigns.
    # This is beyond the scope of a single script without access to such a dataset.
    # Example:
    # if analyzer.historical_data is not None and not analyzer.historical_data.empty:
    #     logging.info("Starting performance validation against historical data...")
    #     # Assuming historical_data has 'subject_line' and 'is_top_quartile' columns
    #     # You would iterate, calculate scores, rank, and compare.
    #     # This part would involve more complex data processing and statistical analysis.
    #     logging.info("Performance validation complete (conceptual).")
    # else:
    #     logging.warning("No historical data provided for performance validation.")
