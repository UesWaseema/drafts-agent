# Email Campaign Guidelines v1

Based on Phase 1 Data Analysis & Insight Extraction for Interspire data, the following guidelines are recommended:

*   **Subject Length**: 35-55 characters
    *   *Evidence*: Length 30-60 chars (peak 50-60 => 0.62 open-rate)

*   **Capitalization Percentage in Subject**: 10-20%
    *   *Evidence*: 10-20 % capitals (+45 % open uplift)
    *   *Evidence*: Caps > 30 % ⇒ 13× bounces (0.17 vs 0.013)

*   **Punctuation Limit in Subject**: 1
    *   *Evidence*: (Implicit from `excess_exclaim` feature, aiming for concise subjects)

*   **Introductory Word Count**: <= 40 words
    *   *Evidence*: ≤40-word intro + single CTA doubles CTR (0.10 vs 0.05)

*   **HTML Bullet Lists**: Required in first half
    *   *Evidence*: HTML bullet lists in first half ⇒ +14 % clicks

*   **External Domains**: <= 2
    *   *Evidence*: ≥3 external domains ⇒ +9 % spam complaints

*   **Domain Alignment**: From-domain == return-path-domain
    *   *Evidence*: From-email domain ≠ sending domain ⇒ bounce 0.028 vs 0.012
