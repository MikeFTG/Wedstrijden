name: Fetch Match Data

on:
  schedule:
    - cron: '0 * * * *'
  workflow_dispatch:

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Fetch wedstrijden van API
        env:
          FOOTBALL_API_KEY: ${{ secrets.FOOTBALL_API_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
        run: |
          echo "API key lengte: ${#FOOTBALL_API_KEY}"
          pip install requests -q
          python3 fetch_matches.py

      - name: Commit en push data
        run: |
          git config user.name "Match Bot"
          git config user.email "bot@match-monitor"
          git add matches.json known_matches.json || true
          git diff --staged --quiet || git commit -m "Update wedstrijddata"
          git push
