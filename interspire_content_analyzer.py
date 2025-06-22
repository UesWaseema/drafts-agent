import re
import html
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class InterspireContentAnalyzer:
    """
    Analyzes email body content patterns to correlate with high engagement based on
    validated historical Interspire campaign analysis.
    """

    def __init__(self, historical_data=None):
        """
        Initializes the InterspireContentAnalyzer with optional historical data.

        Args:
            historical_data (pd.DataFrame, optional): DataFrame containing historical
                                                     Interspire campaign performance data.
        """
        self.historical_data = historical_data
        logging.info("InterspireContentAnalyzer initialized.")

    def _clean_html(self, content):
        """Removes HTML tags and converts HTML entities to plain text."""
        if not isinstance(content, str):
            return ""
        soup = BeautifulSoup(content, 'html.parser')
        return html.unescape(soup.get_text(separator=' ', strip=True))

    def _extract_first_paragraph(self, email_content):
        """
        Extracts the first paragraph/section from HTML or plain text content.
        Considers up to the first HTML break (<br>, <p>, <div>) or 100 words.
        """
        if not isinstance(email_content, str):
            return ""

        soup = BeautifulSoup(email_content, 'html.parser')
        
        # Try to find the first block-level element or a <br>
        first_block = soup.find(['p', 'div', 'br'])
        if first_block:
            intro_text = ""
            for sibling in first_block.previous_siblings:
                if sibling.name in ['p', 'div', 'br']: # Stop at previous block
                    break
                if sibling.string:
                    intro_text = str(sibling.string) + intro_text
            if first_block.string:
                intro_text += str(first_block.string)
            
            # If the first block is a <br>, take text until the next block or end
            if first_block.name == 'br':
                current_element = first_block.next_sibling
                while current_element and current_element.name not in ['p', 'div']:
                    if current_element.string:
                        intro_text += str(current_element.string)
                    current_element = current_element.next_sibling
            
            intro_text = self._clean_html(intro_text).strip()
        else:
            # If no block elements, take the first 100 words of the cleaned text
            intro_text = self._clean_html(email_content)
        
        words = intro_text.split()
        return " ".join(words[:100]) # Limit to 100 words for intro extraction

    def analyze_intro_length(self, email_content):
        """
        Analyzes the length of the email's introduction.

        Args:
            email_content (str): The full content of the email (HTML or plain text).

        Returns:
            dict: Analysis results including word count, optimal status, performance impact, and score contribution.
        """
        try:
            intro_text = self._extract_first_paragraph(email_content)
            word_count = len(intro_text.split())

            optimal_length = word_count <= 40
            performance_impact = "Optimal (doubles click-through)" if optimal_length else \
                                 "Suboptimal (potential negative impact)" if word_count > 60 else \
                                 "Acceptable"

            intro_score = 20 if word_count <= 40 else (5 if word_count <= 60 else -15)

            return {
                'word_count': word_count,
                'optimal_length': optimal_length,
                'performance_impact': performance_impact,
                'score_contribution': float(intro_score)
            }
        except Exception as e:
            logging.error(f"Error analyzing intro length: {e}")
            return {
                'word_count': 0,
                'optimal_length': False,
                'performance_impact': "Error during analysis",
                'score_contribution': 0.0
            }

    def detect_bullet_lists(self, email_content):
        """
        Detects the presence and position of HTML bullet lists.

        Args:
            email_content (str): The full content of the email (HTML or plain text).

        Returns:
            dict: Analysis results including bullet presence, position, engagement boost, and score contribution.
        """
        try:
            soup = BeautifulSoup(email_content, 'html.parser')
            list_tags = soup.find_all(['ul', 'ol'])

            bullets_found = len(list_tags) > 0
            position = 'none'
            engagement_boost = 0.0
            score_contribution = 0.0

            if bullets_found:
                # Determine if bullets are in the first half
                content_length = len(email_content)
                first_half_end = content_length / 2

                for tag in list_tags:
                    # Check if the start of the list tag is within the first half
                    # This is a heuristic, more robust would be to check actual rendered position
                    tag_start_index = email_content.find(str(tag))
                    if tag_start_index != -1 and tag_start_index < first_half_end:
                        position = 'first_half'
                        engagement_boost = 0.14 # +14% lift clicks
                        score_contribution = 15.0
                        break
                if position == 'none':
                    position = 'second_half'

            return {
                'bullets_found': bullets_found,
                'position': position,
                'engagement_boost': engagement_boost,
                'score_contribution': float(score_contribution)
            }
        except Exception as e:
            logging.error(f"Error detecting bullet lists: {e}")
            return {
                'bullets_found': False,
                'position': 'error',
                'engagement_boost': 0.0,
                'score_contribution': 0.0
            }

    def count_cta_links(self, email_content):
        """
        Counts clickable links and provides optimization recommendations.

        Args:
            email_content (str): The full content of the email (HTML or plain text).

        Returns:
            dict: Analysis results including CTA count, optimization status, recommendations, and score contribution.
        """
        try:
            soup = BeautifulSoup(email_content, 'html.parser')
            links = soup.find_all('a', href=True)
            cta_count = len(links)

            optimization_status = "Optimal (single prominent CTA)" if cta_count == 1 else \
                                  "Acceptable (two CTAs)" if cta_count == 2 else \
                                  "Suboptimal (multiple CTAs)"

            recommendations = []
            if cta_count > 2:
                recommendations.append("Consider reducing the number of Call-to-Action links to improve focus.")
            elif cta_count == 0:
                recommendations.append("Add a clear Call-to-Action link to guide user engagement.")
            elif cta_count > 0 and cta_count <= 2:
                recommendations.append("Ensure your primary Call-to-Action is prominent.")

            cta_score = 20 if cta_count == 1 else (10 if cta_count == 2 else -10)

            return {
                'cta_count': cta_count,
                'optimization_status': optimization_status,
                'recommendations': recommendations,
                'score_contribution': float(cta_score)
            }
        except Exception as e:
            logging.error(f"Error counting CTA links: {e}")
            return {
                'cta_count': 0,
                'optimization_status': "Error during analysis",
                'recommendations': ["Error during analysis"],
                'score_contribution': 0.0
            }

    def count_external_domains(self, email_content):
        """
        Extracts and counts unique external domains from links.

        Args:
            email_content (str): The full content of the email (HTML or plain text).

        Returns:
            dict: Analysis results including domain count, risk assessment, specific domains found, and score penalty.
        """
        try:
            soup = BeautifulSoup(email_content, 'html.parser')
            links = soup.find_all('a', href=True)
            
            external_domains = set()
            for link in links:
                href = link.get('href')
                if href:
                    parsed_uri = urlparse(href)
                    if parsed_uri.scheme and parsed_uri.netloc and \
                       not parsed_uri.netloc.startswith('mailto:'): # Exclude mailto links
                        # Simple check for external: not current domain (needs context)
                        # For now, assume all non-empty netlocs are external for scoring
                        external_domains.add(parsed_uri.netloc)
            
            domain_count = len(external_domains)
            
            risk_level = "Low"
            score_penalty = 0.0
            if domain_count > 2:
                risk_level = "High (increased spam complaints)"
                score_penalty = -25.0
            elif domain_count > 0:
                risk_level = "Moderate (potential bounce risk)"

            return {
                'external_domain_count': domain_count,
                'domains_found': list(external_domains),
                'risk_level': risk_level,
                'score_penalty': float(score_penalty)
            }
        except Exception as e:
            logging.error(f"Error counting external domains: {e}")
            return {
                'external_domain_count': 0,
                'domains_found': [],
                'risk_level': "Error during analysis",
                'score_penalty': 0.0
            }

    def analyze_content_structure(self, email_content):
        """
        Analyzes the content structure for compliance with optimal patterns.

        Args:
            email_content (str): The full content of the email (HTML or plain text).

        Returns:
            dict: Analysis results including structure compliance, pattern matching, and optimization score.
        """
        try:
            # This is a simplified heuristic. A more advanced analysis would involve
            # NLP or more complex HTML parsing to identify sections.
            # For now, we check for the presence and relative order of key elements.

            intro_analysis = self.analyze_intro_length(email_content)
            bullet_analysis = self.detect_bullet_lists(email_content)
            cta_analysis = self.count_cta_links(email_content)

            optimal_structure = False
            structure_type = "Suboptimal"
            optimization_score = 0.0

            # Check for intro + bullets + single CTA pattern
            if intro_analysis['optimal_length'] and \
               bullet_analysis['bullets_found'] and \
               bullet_analysis['position'] == 'first_half' and \
               cta_analysis['cta_count'] == 1:
                optimal_structure = True
                structure_type = "Optimal (intro + bullets + single CTA)"
                optimization_score = 10.0 # structure_bonus

            return {
                'pattern_compliance': optimal_structure,
                'structure_type': structure_type,
                'optimization_score': float(optimization_score)
            }
        except Exception as e:
            logging.error(f"Error analyzing content structure: {e}")
            return {
                'pattern_compliance': False,
                'structure_type': "Error during analysis",
                'optimization_score': 0.0
            }

    def assess_html_quality(self, email_content):
        """
        Assesses the HTML quality, including validation, formatting, and mobile-friendliness.

        Args:
            email_content (str): The full content of the email (HTML or plain text).

        Returns:
            dict: Analysis results including validation score, formatting issues, and mobile-friendliness.
        """
        try:
            soup = BeautifulSoup(email_content, 'html.parser')
            
            # Basic HTML validation: check for common structural tags
            has_html = bool(soup.find('html'))
            has_body = bool(soup.find('body'))
            has_head = bool(soup.find('head'))

            validation_score = 0.0
            formatting_issues = []

            if has_html and has_body:
                validation_score += 5
            else:
                formatting_issues.append("Missing fundamental HTML or BODY tags.")
            
            # Check for common formatting issues (e.g., unclosed tags - BeautifulSoup handles many, but can check for others)
            # This is a very basic check. A full HTML validator would be more complex.
            # For example, check for inline styles that might be better in CSS
            if soup.find_all(style=True):
                formatting_issues.append("Extensive use of inline styles detected. Consider external CSS for better maintainability.")

            # Mobile-friendliness indicators (very basic heuristic)
            # Look for viewport meta tag
            mobile_friendly = bool(soup.find('meta', attrs={'name': 'viewport'}))
            if not mobile_friendly:
                formatting_issues.append("Viewport meta tag not found. May impact mobile responsiveness.")
            
            # Score based on presence of good practices
            if not formatting_issues:
                validation_score += 10 # Bonus for clean HTML
            
            # Cap HTML quality score to 15 as per requirements (0-15 range)
            html_quality_score = min(15, validation_score)

            return {
                'validation_score': float(html_quality_score),
                'formatting_issues': formatting_issues,
                'mobile_friendly': mobile_friendly
            }
        except Exception as e:
            logging.error(f"Error assessing HTML quality: {e}")
            return {
                'validation_score': 0.0,
                'formatting_issues': ["Error during analysis"],
                'mobile_friendly': False
            }

    def calculate_content_score(self, email_content):
        """
        Calculates the composite content score (0-100) for 30% weight.

        Args:
            email_content (str): The full content of the email (HTML or plain text).

        Returns:
            float: The composite content score.
        """
        try:
            intro_analysis = self.analyze_intro_length(email_content)
            bullet_analysis = self.detect_bullet_lists(email_content)
            cta_analysis = self.count_cta_links(email_content)
            domain_analysis = self.count_external_domains(email_content)
            structure_analysis = self.analyze_content_structure(email_content)
            html_quality_assessment = self.assess_html_quality(email_content)

            intro_score = intro_analysis['score_contribution']
            bullet_score = bullet_analysis['score_contribution']
            cta_score = cta_analysis['score_contribution']
            domain_penalty = domain_analysis['score_penalty']
            structure_bonus = structure_analysis['optimization_score']
            html_quality = html_quality_assessment['validation_score']

            # Base score can be adjusted, starting at 50 for a neutral email
            base_score = 50 
            
            content_score = base_score + intro_score + bullet_score + cta_score + \
                            domain_penalty + structure_bonus + html_quality

            # Ensure score is within 0-100 range
            final_content_score = max(0, min(100, content_score))
            return float(final_content_score)
        except Exception as e:
            logging.error(f"Error calculating content score: {e}")
            return 0.0

    def generate_content_feedback(self, email_content):
        """
        Generates a list of actionable content improvements.

        Args:
            email_content (str): The full content of the email (HTML or plain text).

        Returns:
            list: A list of strings, each representing an actionable improvement.
        """
        feedback = []
        try:
            intro_analysis = self.analyze_intro_length(email_content)
            bullet_analysis = self.detect_bullet_lists(email_content)
            cta_analysis = self.count_cta_links(email_content)
            domain_analysis = self.count_external_domains(email_content)
            structure_analysis = self.analyze_content_structure(email_content)
            html_quality_assessment = self.assess_html_quality(email_content)

            if not intro_analysis['optimal_length']:
                feedback.append(f"Shorten your introduction. Current length: {intro_analysis['word_count']} words. Aim for <=40 words for optimal click-through.")
            
            if not bullet_analysis['bullets_found'] or bullet_analysis['position'] != 'first_half':
                feedback.append("Consider adding HTML bullet lists in the first half of your email content to boost engagement.")
            
            feedback.extend(cta_analysis['recommendations']) # Add CTA specific recommendations

            if domain_analysis['external_domain_count'] > 2:
                feedback.append(f"Reduce the number of external domains ({domain_analysis['external_domain_count']} found) to mitigate spam complaints and bounce risk.")
            
            if not structure_analysis['pattern_compliance']:
                feedback.append("Optimize content structure: aim for an 'intro + bullets + single CTA' pattern for better readability and engagement.")
            
            if html_quality_assessment['formatting_issues']:
                feedback.append("Address HTML formatting issues for improved deliverability and mobile-friendliness:")
                feedback.extend([f"- {issue}" for issue in html_quality_assessment['formatting_issues']])
            
            if not feedback:
                feedback.append("Content analysis indicates good practices. Keep up the great work!")

        except Exception as e:
            logging.error(f"Error generating content feedback: {e}")
            feedback.append("An error occurred while generating feedback.")
        return feedback

    def validate_content_rules(self, email_content):
        """
        Validates content rules and provides optimization suggestions.

        Args:
            email_content (str): The full content of the email (HTML or plain text).

        Returns:
            dict: Rule compliance report and optimization suggestions.
        """
        try:
            intro_analysis = self.analyze_intro_length(email_content)
            bullet_analysis = self.detect_bullet_lists(email_content)
            cta_analysis = self.count_cta_links(email_content)
            domain_analysis = self.count_external_domains(email_content)
            structure_analysis = self.analyze_content_structure(email_content)
            html_quality_assessment = self.assess_html_quality(email_content)

            rule_compliance = {
                'intro_hook_optimal': intro_analysis['optimal_length'],
                'bullet_lists_early': bullet_analysis['bullets_found'] and bullet_analysis['position'] == 'first_half',
                'single_cta_optimal': cta_analysis['cta_count'] == 1,
                'external_domain_limit_met': domain_analysis['external_domain_count'] <= 2,
                'optimal_content_structure': structure_analysis['pattern_compliance'],
                'html_quality_good': not html_quality_assessment['formatting_issues']
            }

            optimization_suggestions = self.generate_content_feedback(email_content)

            return {
                'rule_compliance_report': rule_compliance,
                'optimization_suggestions': optimization_suggestions
            }
        except Exception as e:
            logging.error(f"Error validating content rules: {e}")
            return {
                'rule_compliance_report': {},
                'optimization_suggestions': ["Error during rule validation."]
            }

    def analyze_email_content(self, email_content):
        """
        Performs a comprehensive analysis of the email content and returns a structured report.

        Args:
            email_content (str): The full content of the email (HTML or plain text).

        Returns:
            dict: A comprehensive analysis report.
        """
        try:
            intro_analysis = self.analyze_intro_length(email_content)
            bullet_analysis = self.detect_bullet_lists(email_content)
            cta_analysis = self.count_cta_links(email_content)
            domain_analysis = self.count_external_domains(email_content)
            structure_analysis = self.analyze_content_structure(email_content)
            html_quality_assessment = self.assess_html_quality(email_content)
            overall_content_score = self.calculate_content_score(email_content)
            content_feedback = self.generate_content_feedback(email_content)
            rule_validation = self.validate_content_rules(email_content)

            # Determine optimization priority based on feedback
            optimization_priority = []
            if not intro_analysis['optimal_length']:
                optimization_priority.append("Shorten Intro Hook")
            if not bullet_analysis['bullets_found'] or bullet_analysis['position'] != 'first_half':
                optimization_priority.append("Add/Move Bullet Lists")
            if cta_analysis['cta_count'] != 1:
                optimization_priority.append("Optimize CTA Count")
            if domain_analysis['external_domain_count'] > 2:
                optimization_priority.append("Reduce External Domains")
            if not structure_analysis['pattern_compliance']:
                optimization_priority.append("Improve Content Structure")
            if html_quality_assessment['formatting_issues']:
                optimization_priority.append("Fix HTML Quality")
            
            # If no specific issues, suggest general improvements
            if not optimization_priority and content_feedback:
                optimization_priority.append("Review General Content Feedback")


            return {
                'intro_analysis': intro_analysis,
                'bullet_analysis': bullet_analysis,
                'cta_analysis': cta_analysis,
                'domain_analysis': domain_analysis,
                'structure_analysis': structure_analysis,
                'html_quality': html_quality_assessment,
                'overall_content_score': overall_content_score,
                'content_feedback': content_feedback,
                'optimization_priority': optimization_priority
            }
        except Exception as e:
            logging.error(f"Error during comprehensive email content analysis: {e}")
            return {
                'intro_analysis': {},
                'bullet_analysis': {},
                'cta_analysis': {},
                'domain_analysis': {},
                'structure_analysis': {},
                'html_quality': {},
                'overall_content_score': 0.0,
                'content_feedback': ["An error occurred during analysis."],
                'optimization_priority': ["Error"]
            }

# Example Usage
if __name__ == "__main__":
    analyzer = InterspireContentAnalyzer()

    sample_html_email_good = """
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Your Exclusive Offer!</title>
    </head>
    <body>
        <p>Hi there!</p>
        <p>
            This is a short and sweet introduction to our amazing new product.
            We've been working hard to bring you something truly special that
            will revolutionize the way you experience daily tasks. It's designed
            with you in mind, focusing on simplicity and efficiency.
        </p>
        <ul>
            <li>Benefit 1: Save time every day</li>
            <li>Benefit 2: Boost your productivity</li>
            <li>Benefit 3: Enjoy a seamless experience</li>
        </ul>
        <p>Don't miss out on this limited-time opportunity!</p>
        <p><a href="https://www.example.com/buy-now" style="background-color:blue; color:white; padding:10px 20px; text-decoration:none;">Click Here to Get Started!</a></p>
        <p>Visit us at <a href="https://www.example.com">Our Website</a></p>
    </body>
    </html>
    """

    sample_html_email_bad = """
    <html>
    <head>
        <title>A Very Long and Detailed Email Subject That Goes On and On and On</title>
    </head>
    <body>
        <h1>Welcome to Our Newsletter!</h1>
        <p>
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
            Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
            Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
            Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
            This introduction is intentionally very long to test the analyzer's word count limits.
            We have so much to tell you about our company, our history, and our future plans.
            Stay tuned for more updates!
        </p>
        <p>Check out these links:</p>
        <a href="https://www.external-site-1.com/page1">Link 1</a><br>
        <a href="https://www.external-site-2.com/page2">Link 2</a><br>
        <a href="https://www.external-site-3.com/page3">Link 3</a><br>
        <a href="https://www.external-site-4.com/page4">Link 4</a><br>
        <p>And also visit our partners:</p>
        <a href="https://www.partner-site.com">Partner Site</a>
        <p>No bullet lists here!</p>
        <div>
            <span>Some unformatted text.</span>
        </div>
    </body>
    </html>
    """

    sample_plain_text_email = """
    Hi Team,

    This is a plain text email for testing purposes.
    It has a short intro.

    - Item one
    - Item two
    - Item three

    Please click here: https://www.plaintext-cta.com

    Thanks,
    The Team
    """

    print("--- Analyzing Good HTML Email ---")
    analysis_good = analyzer.analyze_email_content(sample_html_email_good)
    for key, value in analysis_good.items():
        print(f"{key}: {value}")
    print("\n")

    print("--- Analyzing Bad HTML Email ---")
    analysis_bad = analyzer.analyze_email_content(sample_html_email_bad)
    for key, value in analysis_bad.items():
        print(f"{key}: {value}")
    print("\n")

    print("--- Analyzing Plain Text Email ---")
    analysis_plain = analyzer.analyze_email_content(sample_plain_text_email)
    for key, value in analysis_plain.items():
        print(f"{key}: {value}")
    print("\n")
