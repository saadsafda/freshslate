# What I Need From You

**To:** Dr. Marigny
**From:** Shayan
**Date:** 2026-08-10

---

Here's where things stand and what I need from you to keep moving.

I've split it into two parts: **things only you can answer** (quick), and **things I need you to
send me** (a bit more work). Nothing here needs technical knowledge — if a question doesn't make
sense, just tell me and I'll rephrase it.

---

# PART 1 — Questions only you can answer

## Question 1: Who is the phone agent calling?

You told me earlier: **realtors, not homeowners.**

But the playbook you sent has the phone agent calling **property owners** — the people in tax
trouble.

**These have to be kept completely separate**, because the rules are different:

- **Calling realtors** — this is business-to-business. Normal rules.
- **Calling homeowners in distress** — the Do Not Call list applies. Fines run about
  **$500 to $1,500 per phone call**, and one bad list can be thousands of calls.

**What I need:** just tell me which one we're building first. Realtors or homeowners.

If it's both eventually, that's fine — but they need to be built as two separate systems so a
homeowner never accidentally gets called by the realtor system.

---

## Question 2: Are you legally cleared to make these calls yet?

Your own playbook says:

> *"Test target for today: your own phone only. A2P and DNC aren't cleared. Three consenting
> friends maximum."*

Plain English: **as of when you wrote that, you were not cleared to call real people yet.**

**What I need:** is that still true, or has it been sorted?

Three things have to be in place before the first real call:

1. **Phone registration** — carriers require registration before automated calls go out.
   Sometimes your phone provider handles this. Do you know if it's done?
2. **Do Not Call list checking** — someone has to check every number against the national Do Not
   Call list before dialing. Is anyone doing this?
3. **Recording permission** — if calls are recorded, the greeting has to say so. Has a lawyer
   approved that wording?

If the answer to any of these is "I don't know," that's a completely fine answer — just say so
and we'll find out together. **I'd rather ask now than after the first fine.**

---

## Question 3: Who is your lawyer?

There's a new Louisiana law — **Act 807** — that started **August 1st**. It changes how
wholesaling contracts have to be written. Fines up to **$5,000 each time**, and a contract that
misses a required piece **can be cancelled by the seller** any time before closing.

Here's my problem: **I have two different answers about one of the rules and I can't tell which
is right.**

The law says a seller can change their mind and cancel after signing. But:

- One source says they get **5 days**
- Another says **14 days**

I tried to look up the actual law text online and the Louisiana government website wouldn't
load. **I'm not willing to guess on this** — if we put the wrong number in your contracts, every
contract you sign could be cancelled.

**What I need:** the name of your Louisiana real estate attorney, and when they can look at this.

It should take them about 20 minutes. They just need to read the actual law and tell me the
right number.

---

# PART 2 — Things I need you to send me

## 1. Your repair cost numbers ← **the biggest one**

I built the tool that estimates repair costs and calculates your offer price. It works. **But
right now it's using made-up numbers that I invented**, because I don't know what things
actually cost you.

Every estimate it produces currently has a warning stamped on it saying "these are fake numbers,
don't use this to make a real offer."

**What I need:** what you actually pay for things. For example:

- A roof — what do you pay per square?
- A full kitchen — what does that run you?
- A full bathroom gut and rebuild?
- HVAC unit?
- Water heater?
- Rewiring a house?
- Leveling piers?
- Flooring, per square foot?
- Paint, per square foot?

Also:

- **What percentage do you use for your offer formula?** Right now I have it set to 70% of the
  after-repair value, minus repairs, minus your fee. Is 70% right? Does it change by parish or
  by price range?
- **What's your typical assignment fee?** I have $12,500 as a placeholder.
- **How much do you add for surprises?** I have 15%.

**Any format works.** A spreadsheet, a photo of a handwritten list, an old estimate you did, or
just typing them in an email. Whatever's easiest.

**This is the single most valuable thing you can send me.** The moment I have your numbers, the
tool produces real offers instead of warnings.

---

## 2. GoHighLevel access — so the phone agent can save call results

The phone agent needs somewhere to write down what happened on each call. You said that's
GoHighLevel.

I need four things. **All of them you can get by clicking around in GoHighLevel** — no technical
skill needed.

### a) Your account ID and a password for the system

In GoHighLevel: **Settings → Business Profile**. There's an ID number there — send me that.

Then: **Settings → Integrations** (or "API Keys"). You'll create a key there. It's like a
password that lets my system write into your CRM.

> ⚠️ **Please don't email me the key.** Anyone who gets it can read your whole CRM. Send it
> through a password manager, or text it separately from everything else, or just tell me and
> I'll walk you through putting it in directly.

### b) Your pipeline stages

In GoHighLevel, go to **Opportunities**. You'll see columns across the top — things like "New
Lead," "Contacted," "Appointment Set."

**Just screenshot that screen and send it.** I need to know the exact names and their order.

Also tell me: **when a call finishes, which column should the person move into?**

### c) Your custom fields

Go to **Settings → Custom Fields**. **Screenshot the whole list.**

I need to know exactly what boxes exist to store information, because the names have to match
exactly. If I guess "phone_result" and yours is called "call_outcome," nothing saves.

If the list is empty or missing things, tell me — I'll send you a list of what to create.

### d) What happens when someone says "stop calling me" ← **most important**

This one matters more than the rest.

When someone tells the agent to stop calling:

- Where does that get recorded in GoHighLevel?
- **Does anything stop them from being called again?**

If someone says stop and gets called again anyway, that's the expensive kind of mistake. If this
isn't set up yet, tell me — **it needs to exist before the first real call**, and I'll help set
it up.

---

## 3. Other documents (whenever you have them — not urgent)

| What | Why I need it |
|---|---|
| Your contract templates — purchase agreement, assignment, as-is addendum | The contract checker needs to check against *your* forms, not generic ones |
| One Succession filing — **cross out the names first** | I only need to see how the document is laid out, not who's in it |
| 2–3 old text messages or postcards you've sent | So the compliance checker can be tested on real material |
| How you organize your deal files | So the reminder system knows where to look |
| Confirm: houses and 2-4 units, $120k–$400k after repair, $10–15k fee — still right? | Making sure I have your buy box correct |

---

# Where things stand right now

**Working today:**

- **Finding distressed properties** — pulling live data from the official City of New Orleans
  and Baton Rouge government databases right now. Real properties, updated daily.
- **Repair estimates and offer calculations** — working, waiting on your real numbers
- **Contract checking** — built, waiting on your lawyer
- **Security testing** — 10 out of 10 safety checks passing

**Two things you should know about:**

### 1. The Orleans Assessor website blocks us — and Module 13 tells students to use it

Your Module 13 teaches students to pull data from `nolaassessor.com`. **That site blocks
automated access completely.** It also has a notice saying automated collection isn't allowed.

**If a student tries this during the course, it will fail in front of everyone.** I'd fix that
section before you teach it.

**The good news:** I found a better way. The City of New Orleans and Baton Rouge both publish
official government databases that are free, allowed, and faster. I'm already using them — the
most recent record I pulled was filed the day before I checked. And unlike scraping a website,
this doesn't break when they redesign a page.

### 2. Jefferson Parish doesn't have one of these databases

Orleans and Baton Rouge do. Jefferson doesn't. Getting Jefferson working is a separate job,
roughly 1–2 weeks. **I'd suggest not promising Jefferson until we've scoped it.**

**What it costs to run right now:** the property data is free. The AI costs roughly $90–150 a
month.

---

# If you only do three things this week

1. **Send me your repair cost numbers** — unblocks the biggest piece
2. **Tell me your lawyer's name** — unblocks the contract piece
3. **Answer Question 1 and 2 above** — realtors or homeowners, and whether you're cleared to call

Everything else can wait.

Anything here that doesn't make sense, just ask. Happy to jump on a call and walk through it.
