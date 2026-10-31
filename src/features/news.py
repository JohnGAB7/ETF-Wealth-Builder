from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

def summarize_news(items: list[dict]) -> dict:
    if not items:
        return {"news_sentiment": None, "news_count": 0, "news_coverage": 0.0}
    scores = []
    for item in items:
        title = str(item.get("headline", ""))
        summary = str(item.get("summary", ""))
        text = (title + ". " + summary).strip()
        if text.strip(". "):
            scores.append(_analyzer.polarity_scores(text)["compound"])
    return {
        "news_sentiment": sum(scores) / len(scores) if scores else None,
        "news_count": len(items),
        "news_coverage": 1.0 if scores else 0.0,
    }
