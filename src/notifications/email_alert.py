import os
import smtplib
from email.message import EmailMessage
from src.config import get_secret

def send_email(subject: str, body: str) -> bool:
    host = get_secret("SMTP_HOST")
    username = get_secret("SMTP_USERNAME")
    password = get_secret("SMTP_PASSWORD")
    sender = get_secret("EMAIL_FROM")
    recipient = get_secret("EMAIL_TO")
    port = int(os.getenv("SMTP_PORT", "587"))
    if not all([host, username, password, sender, recipient]):
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, recipient
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
    return True

def send_digest(results: list[dict], run_date: str) -> bool:
    lines = [f"ETF Wealth Builder — rapport quotidien ({run_date})", ""]
    for item in results:
        name = item.get("name", item.get("id", "ETF inconnu"))
        signal = item.get("signal", item.get("status", "N/A"))
        score = item.get("score")
        price = item.get("price")
        lines.append(f"- {name}: {signal}; score={score}; prix={price}")
        if item.get("prob_positive") is not None:
            lines.append(f"  P(rendement positif à horizon du modèle)={item['prob_positive']:.1%}")
        if item.get("expected_return") is not None:
            lines.append(f"  Rendement conditionnel estimé={item['expected_return']:.2%}")
    lines += ["", "Les estimations sont incertaines. Aucune garantie de rendement.",
              "Vérifier les données, frais, fiscalité et allocation avant toute décision."]
    return send_email(f"ETF Wealth Builder | Rapport quotidien | {run_date}", "\n".join(lines))
