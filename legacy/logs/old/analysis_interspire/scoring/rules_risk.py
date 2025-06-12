import json

def calculate_risk_scores(subject_scores: dict, content_scores: dict) -> dict:
    """
    Calculates overall risk and compliance status based on subject and content scores.
    """
    overall_score = 0
    overall_compliance_status = "Compliant"
    per_rule_pass_fail = {}
    optimization_priority_list = []
    feedback_bullets = []

    # Combine all scores for easier processing
    all_scores = {**subject_scores, **content_scores}

    # Define rules and their impact on compliance and overall score
    # For simplicity, let's define some example rules.
    # In a real scenario, these would be more detailed and configurable.

    # Subject Rules
    if all_scores.get("subject_length_score", 0) == -25:
        per_rule_pass_fail["subject_length_pass"] = "Fail"
        overall_compliance_status = "Non-Compliant"
        feedback_bullets.append("Subject line length is not optimal.")
        optimization_priority_list.append("Subject Length")
    else:
        per_rule_pass_fail["subject_length_pass"] = "Pass"
    overall_score += all_scores.get("subject_length_score", 0)

    if all_scores.get("subject_caps_score", 0) == -20:
        per_rule_pass_fail["subject_caps_pass"] = "Fail"
        overall_compliance_status = "Non-Compliant"
        feedback_bullets.append("Subject line has excessive capital letters.")
        optimization_priority_list.append("Subject Capitalization")
    else:
        per_rule_pass_fail["subject_caps_pass"] = "Pass"
    overall_score += all_scores.get("subject_caps_score", 0)

    if all_scores.get("subject_spam_risk_score", 0) < 0:
        per_rule_pass_fail["subject_spam_pass"] = "Fail"
        overall_compliance_status = "Non-Compliant"
        feedback_bullets.append("Subject line contains spam-like keywords.")
        optimization_priority_list.append("Subject Spam Risk")
    else:
        per_rule_pass_fail["subject_spam_pass"] = "Pass"
    overall_score += all_scores.get("subject_spam_risk_score", 0)

    if all_scores.get("subject_punctuation_ok", 1) == 0:
        per_rule_pass_fail["subject_punctuation_pass"] = "Fail"
        overall_compliance_status = "Non-Compliant"
        feedback_bullets.append("Subject line has problematic punctuation (e.g., too many exclamation marks).")
        optimization_priority_list.append("Subject Punctuation")
    else:
        per_rule_pass_fail["subject_punctuation_pass"] = "Pass"
    # subject_overall_score already includes punctuation penalty, so no need to add to overall_score again

    # Content Rules
    if all_scores.get("intro_score", 0) < 0:
        per_rule_pass_fail["intro_pass"] = "Fail"
        feedback_bullets.append("Email intro is not optimal.")
        optimization_priority_list.append("Content Intro")
    else:
        per_rule_pass_fail["intro_pass"] = "Pass"
    overall_score += all_scores.get("intro_score", 0)

    if all_scores.get("cta_score", 0) < 0:
        per_rule_pass_fail["cta_pass"] = "Fail"
        feedback_bullets.append("Email does not have a single clear Call to Action.")
        optimization_priority_list.append("Content CTA")
    else:
        per_rule_pass_fail["cta_pass"] = "Pass"
    overall_score += all_scores.get("cta_score", 0)

    if all_scores.get("external_domains_score", 0) < 0:
        per_rule_pass_fail["external_domains_pass"] = "Fail"
        feedback_bullets.append("Email contains too many external domains.")
        optimization_priority_list.append("Content External Domains")
    else:
        per_rule_pass_fail["external_domains_pass"] = "Pass"
    overall_score += all_scores.get("external_domains_score", 0)

    # HTML Validation (assuming 15 is max score for good validation)
    if all_scores.get("html_validation_score", 0) < 15:
        per_rule_pass_fail["html_validation_pass"] = "Fail"
        feedback_bullets.append("HTML validation issues detected (e.g., missing html/body tags, inline styles, viewport meta).")
        optimization_priority_list.append("HTML Validation")
    else:
        per_rule_pass_fail["html_validation_pass"] = "Pass"
    overall_score += all_scores.get("html_validation_score", 0)

    # Mobile Friendly (assuming 10 is max score for basic mobile friendliness)
    if all_scores.get("mobile_friendly_score", 0) < 10:
        per_rule_pass_fail["mobile_friendly_pass"] = "Fail"
        feedback_bullets.append("Email may not be fully mobile-friendly (missing viewport meta).")
        optimization_priority_list.append("Mobile Friendliness")
    else:
        per_rule_pass_fail["mobile_friendly_pass"] = "Pass"
    overall_score += all_scores.get("mobile_friendly_score", 0)

    # Confidence Level
    if overall_score >= 75:
        confidence_level = "High"
    elif overall_score >= 50:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"

    # Ensure optimization_priority_list has unique items and is ordered
    optimization_priority_list = sorted(list(set(optimization_priority_list)))

    return {
        "overall_compliance_status": overall_compliance_status,
        "per_rule_pass_fail": per_rule_pass_fail, # This will be a nested dict
        "overall_score": overall_score,
        "confidence_level": confidence_level,
        "optimization_priority_list": optimization_priority_list,
        "feedback_json": json.dumps(feedback_bullets), # Store as JSON string
        "optimizer_version": "interspire_rules_v1",
    }

if __name__ == "__main__":
    # Example usage
    # Create dummy subject and content scores for testing
    dummy_subject_scores_good = {
        "subject_length_score": 30,
        "subject_caps_score": 0,
        "subject_spam_risk_score": 0,
        "subject_keyword_score": 5,
        "subject_punctuation_ok": 1,
        "subject_overall_score": 35,
    }

    dummy_content_scores_good = {
        "intro_score": 20,
        "bullets_score": 10,
        "cta_score": 20,
        "external_domains_score": 15,
        "structure_score": 10,
        "html_validation_score": 15,
        "mobile_friendly_score": 10,
        "email_content_score": 100,
    }

    dummy_subject_scores_bad = {
        "subject_length_score": -25,
        "subject_caps_score": -20,
        "subject_spam_risk_score": -10,
        "subject_keyword_score": 0,
        "subject_punctuation_ok": 0,
        "subject_overall_score": -70,
    }

    dummy_content_scores_bad = {
        "intro_score": -10,
        "bullets_score": 0,
        "cta_score": -10,
        "external_domains_score": -5,
        "structure_score": 0,
        "html_validation_score": 0,
        "mobile_friendly_score": 0,
        "email_content_score": -35,
    }

    print("--- Good Scores Example ---")
    risk_analysis_good = calculate_risk_scores(dummy_subject_scores_good, dummy_content_scores_good)
    for k, v in risk_analysis_good.items():
        if k == "per_rule_pass_fail":
            print(f"{k}: {json.dumps(v, indent=2)}")
        elif k == "feedback_json":
            print(f"{k}: {json.loads(v)}")
        else:
            print(f"{k}: {v}")

    print("\n--- Bad Scores Example ---")
    risk_analysis_bad = calculate_risk_scores(dummy_subject_scores_bad, dummy_content_scores_bad)
    for k, v in risk_analysis_bad.items():
        if k == "per_rule_pass_fail":
            print(f"{k}: {json.dumps(v, indent=2)}")
        elif k == "feedback_json":
            print(f"{k}: {json.loads(v)}")
        else:
            print(f"{k}: {v}")
