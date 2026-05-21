# DynaMo — Context-Aware Ad Campaign System

**Live dashboard:** https://dynamo-bpx7cyoalddxpzxps3jzec.streamlit.app/

DynaMo runs ad campaigns that turn on and off based on real-world conditions. For this MVP the signal is weather: it watches temperature and rainfall across four Indian cities (Mumbai, Delhi, Bangalore, Chennai) and automatically decides which ad creative should run in each city, so a marketer never has to switch creatives by hand.

Built for CoolSip, a beverage brand running a summer campaign with three creatives: "Beat the Heat" (when hot), "Rainy Day Pick-Me-Up" (when raining), and "Refresh Anytime" (otherwise).

## How it works

A scheduled job fetches live weather every 12 minutes, evaluates a set of rules, flips the matching line items active or paused, and logs every change with its reason. A dashboard gives the CoolSip team full visibility into what is running where and why.

## Stack

- **Database:** Supabase (line items, creatives, rules, weather readings, change log, cities)
- **Backend:** Python decision job (fetch → evaluate rules → update state → log)
- **Scheduler:** Supabase Edge Functions / GitHub Actions, runs every 12 minutes
- **Weather:** Open-Meteo API
- **Dashboard:** Streamlit

## Key features

- Rules-based decision engine with priority handling (Rainy > Hot > Normal)
- Full audit trail of every state change (system vs manual)
- Manual override and emergency pause-all controls
- Per-city data freshness indicators
- Configured-policy view for outage handling and CMO alerts

Built as a Product Manager assessment for YOptima.

