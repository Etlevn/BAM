"""Paper-reproduction regressions (locked FE specs).

Run via root ``research.py`` (``GROUPS`` + ``RUN_*``); modules here are not CLI entries.

Paper table map (Submission v5):

| Module                 | Table | Meaning |
|------------------------|-------|---------|
| ``disposition``        | 2     | Disposition Effect — 处置效应：浮盈时更愿卖出 |
| ``extrapolation``      | 3     | Return Extrapolation — 收益外推：用近期收益解释预期收益 |
| ``belief_action``      | 4     | Belief–Action Coupling — 信念—行动：预期收益 → 下期买入 |
| ``bid_offer``          | 5     | Bid–Offer Gap — 买卖缺口 → 下期价格变化 |
| ``disagreement``       | 6     | Disagreement & Volume — 预期分歧 → 成交金额 |
| ``stated_belief``      | 7     | Reasoning → Beliefs — 文字买卖意向 → 预期收益 |
| ``stated_action``      | 8     | Reasoning → Trading — 文字买卖意向 → 下期买入 |
| ``mechanism_bubble``   | 9     | Mechanisms in Bubble — 泡沫期 vs 非泡沫期机制评分 |

Tables 1 / 10 / 11 live in ``anal.py`` / NLP (not this package).
"""
