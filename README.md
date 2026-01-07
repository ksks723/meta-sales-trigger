🚀 Meta-Sales Trigger Intelligence System

스타트업의 성장 신호(투자, 채용)를 분석하여 영업 우선순위를 자동 도출하는 세일즈 인텔리전스 엔진입니다.

## 🛠️ Tech Stack
- **Language**: Python 3.x
- **Database**: SQLite (3-Layer Architecture: Raw, Signal, Mart)
- **Logic**: Rule-based Scoring System

## 📂 Project Structure
- `src/`: Backend logic and data pipeline
- `data/`: Local database storage (ignored in Git)

## 📈 Scoring Engine Logic
- Funding (Series A): +30pt
- Hiring (Sales/Marketing): +25pt / +20pt
- Recency (Within 3 months): +10pt
