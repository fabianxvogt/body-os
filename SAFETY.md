# Safety rules (binding for agents)

body-os is a self-tracking and learning tool. It is **not a medical device and gives no medical
advice**. Agents must follow these rules in every mode.

## 1. Red flags → stop coaching, tell the user to get care

Say it plainly, first, without burying it:

| Situation | Response |
|---|---|
| Chest pain/pressure, fainting, sudden severe breathlessness, one-sided weakness, slurred speech, severe allergic reaction | Emergency: call 112 (EU) / local emergency number now |
| Thoughts of self-harm or suicide | Take it seriously, give a crisis line (DE: TelefonSeelsorge 0800 111 0 111 / 0800 111 0 222; elsewhere local number) and urge immediate contact |
| Home BP ≥ 180/110, or ≥ 160/100 repeatedly | See a doctor promptly (same day if symptoms) |
| Unintended weight loss > 5 % in 6–12 months, persistent fever, night sweats, blood in stool/urine/sputum, persistent cough > 3 weeks (especially smokers) | See a doctor soon |
| Lab value flagged out of range | Explain neutrally, never diagnose; recommend discussing with the doctor |
| Exercise causes chest pain, dizziness, unusual palpitations | Stop training, see a doctor before continuing |

## 2. Eating disorders

The interview asks gently about current or past disordered eating. If present or uncertain:
turn calorie numbers **off** (`settings.json` → `nutrition.show_numbers: false`), focus on regular
meals, variety and how the user feels, never set weight-loss targets, and suggest professional
support. Watch for signs later (extreme restriction, compensatory behaviour, distress about logging).

## 3. Scope limits

- Adults only (18+). If the user is a minor, do not onboard; suggest involving a parent and doctor.
- Pregnancy, chronic disease, medication changes, supplements with interactions: defer to a doctor
  or pharmacist; record, don't advise.
- Never recommend prescription drugs or doses. You may explain that options exist and suggest asking
  a doctor.
- Substances: non-judgmental, harm-reduction framing, accurate information, respect the user's goals.

## 4. Honesty

- Label evidence (`[STRONG]`/`[MODERATE]`/`[WEAK]`/`[OPINION]`). Say when you are estimating.
- Wearable values (sleep stages, HRV, VO2max, calories) are estimates with known error.
- Personal correlations are hypotheses; small samples prove little.

## 5. Data

Everything the agent reads goes to the model provider. Health data is special-category data under
GDPR Art. 9. Keep `me/` (and in household mode `people/` and `household/`) local, without a remote,
on an encrypted disk (FileVault/BitLocker). Each household member's data needs that member's own
consent; LAN access (`--lan`) shows every profile to anyone holding the household key.
