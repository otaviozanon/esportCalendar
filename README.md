# 📅 EsportCalendar

Automatic esports calendar generator in iCalendar format (.ics). Tracks matches from CS2, Valorant, League of Legends, and Rocket League from Brazilian teams.

## 📖 About

`esportCalendar` is a Python script that automates the creation of iCalendar (.ics) files for esports events. It solves the challenge of manually tracking tournaments and esports matches across different platforms, simplifying the process by scraping data from [tips.gg](https://tips.gg) and generating a calendar file compatible with Google Calendar, Outlook, and Apple Calendar.

**Target audience:** Esports enthusiasts, professional players, teams, and organizations who want to track events without manual entry.

## ✨ Features

- 🎯 **Automatic Generation**: Creates iCalendar (.ics) files from esports event data
- 🌐 **Web Scraping**: Extracts event information from [tips.gg](https://tips.gg) using Scrape.do
- 📅 **iCalendar Format**: Generates calendars in standard format, compatible with any calendar application
- 🎮 **Multiple Esports**: Supports CS2, Valorant, League of Legends, and Rocket League
- 🇧🇷 **Brazilian Teams**: Tracks specific Brazilian teams in each game
- ⚡ **Efficient Execution**: ~990 requests/month (1000 limit)
- 🔄 **Scheduling**: Runs every 48 minutes via GitHub Actions
- 🪶 **Lightweight**: No heavy dependencies (no Selenium/ChromeDriver)
- 🔔 **Reminders**: Adds alerts 15 minutes before each event

## 🚀 Quick Start

```bash
git clone https://github.com/otaviozanon/esportCalendar.git
cd esportCalendar
pip install -r requirements.txt
python generate_ics.py
```

This will generate a `calendar.ics` file that you can import into your calendar.

## 📦 Installation

### Prerequisites
- Python 3.8+
- pip
- [Scrape.do](https://scrape.do) account (API key)

### Steps

1. **Clone the repository:**

```bash
git clone https://github.com/otaviozanon/esportCalendar.git
cd esportCalendar
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Configure Scrape.do API key:**

```bash
export SCRAPE_DO_API_KEY="your_api_key_here"
```

4. **Run the script:**

```bash
python generate_ics.py
```

5. **Import the calendar:**

Open the generated `calendar.ics` file and import it into your favorite calendar application (Google Calendar, Outlook, Apple Calendar, etc).

## ⚙️ Configuration

### Environment Variables

```bash
SCRAPE_DO_API_KEY  # Your Scrape.do API key (required)
```

### Customizing Teams

Edit the `GAMES` dictionary in `generate_ics.py` to add or remove teams:

```python
GAMES = {
    "CS2": {
        "prefix": "[CS2] ",
        "base_path": "https://tips.gg/csgo/matches/",
        "days_to_scrape": 3,
        "once_per_day": False,
        "teams": {"FURIA", "paiN Gaming", "MIBR", ...},
        "exclusions": {"Imperial.A", "Imperial Fe", ...},
    },
    # ... other esports
}
```

## 📊 Output

The `calendar.ics` file contains:
- ✅ Event name (ex: `[CS2] FURIA vs MIBR`)
- ✅ Date and time (São Paulo timezone)
- ✅ Description with tournament and link
- ✅ 15-minute reminder
- ✅ Event URL

## 🎯 Execution Logic

### CS2
- Scrapes the next 3 days
- Runs every time the script executes
- Rotative: day 1 → day 2 → day 3 → day 1

### Valorant, LOL, RL
- Scrapes only the current day
- Runs only 1x per day (starting at 00:00)
- Stores execution state in `state.json`

## ❓ FAQ

**Q: Why Scrape.do instead of Selenium?**
A: Scrape.do is faster, more reliable (99.98% uptime), and doesn't require heavy ChromeDriver.

**Q: How do I add new esports?**
A: Add an entry to the `GAMES` dictionary with the tips.gg base_path and desired teams.

**Q: Can I use this offline?**
A: No, the script needs internet access to reach tips.gg via Scrape.do.

**Q: What timezone is used?**
A: America/Sao_Paulo (BRT)

**Q: How do I import the calendar?**
A: Open the `calendar.ics` file and import it into your calendar (Google Calendar, Outlook, Apple Calendar, etc) || Or if wanna use this calendar, use subscribe calendar: `https://is.gd/EsportCalendar`

**Q: Can I add more teams?**
A: Yes, edit the `teams` list for each esport in the `GAMES` dictionary.

## 📝 License

This project is under the MIT License. See the LICENSE file for details.

## 🙏 Acknowledgments

- [tips.gg](https://tips.gg) - Esports data source
- [Scrape.do](https://scrape.do) - Web scraping API
- [icalendar](https://github.com/icalendar/icalendar) - .ics file generation
- [requests](https://github.com/psf/requests) - HTTP requests
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [pytz](https://pypi.org/project/pytz/) - Timezone management
