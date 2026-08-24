# KarosL User Guide

A simple guide to using KarosL to manage your properties, occupants, and payments. No technical knowledge
needed.

## Logging in

1. Open KarosL in your browser. You'll see a sign-in screen titled **"KarosL"** with the subtitle
   **"Property Management."**
2. Enter your **Username** and **Password**.
3. Click **Sign in**. While it's checking your details, the button will say **"Signing in…"**
4. If your details are wrong, a message will appear above the fields explaining the problem.
5. Once you're signed in, you'll land on the **Overview** page (the Dashboard).

Your access depends on your role:
- **Property Manager** — you can view everything and create/edit occupants, payments, and property
  details.
- **Staff** — you can view properties, units, and reports, but you cannot create or change occupants,
  payments, or occupancy records.
- **Super Administrator** — full access, including managing user accounts.

If a button or page you expect to see isn't there, it's most likely because your role doesn't have access
to it — this is normal and by design, not an error.

## The Dashboard (Overview page)

When you log in, you'll see:
- **Occupied Beds** — how many beds are occupied out of total capacity, with a link to **View Property
  Map** (this takes you to Property Explorer).
- **Outstanding Payments** — how many occupants currently owe money, and the total amount (Property
  Manager and above only).
- **Occupants** — how many occupants are registered, and how many are active.
- **Quick Actions** — shortcut buttons: **Register Occupant** and **Record Payment** (Property Manager and
  above only), and **Browse Explorer** (everyone).
- **Properties Overview** — a quick summary card for each property.
- **Recent Payments** — the latest payments recorded (Property Manager and above).
- **Recent Activity** — a live feed of recent actions taken in the system (visible to Super Administrators).

## Registering a new occupant

1. Click **Register Occupant** on the Dashboard, or go to the **Occupants** page and click **Add
   Occupant**.
2. Fill in the form:
   - **First Name** and **Last Name** — required.
   - **Email**, **Phone**, **Student ID**, **National ID** — all optional.
3. Click **Add Occupant** to save.
4. You'll see a confirmation message ("Occupant created successfully.") and be taken back to the Occupants
   list.

If you leave a required field empty, or type something invalid (like a badly-formatted email or phone
number), you'll see a short red message under that specific field telling you what to fix.

## Assigning accommodation to an occupant

1. Open the occupant's profile (find them via the **Occupants** page, see "Finding an occupant" below).
2. Click **Assign to Unit**.
3. A step-by-step window opens:
   - **Step 1 — Select Property**: click the property you want.
   - **Step 2 — Select Section**: click the section within that property.
   - **Step 3 — Select Unit**: click an available unit. Full units are shown as **"(Full)"** and can't be
     selected.
4. Once you've picked a unit, confirm the assignment:
   - **Start Date** — defaults to today, but you can change it.
   - **Billing Mode** — choose **Semester** or **Monthly**.
5. Click **Assign Unit** to confirm.

You can click **← Back** at any point to change an earlier choice.

## Recording a payment

1. From the occupant's profile, click **Record Payment** — or use the **Record Payment** quick action on
   the Dashboard and pick the occupant from the list that appears.
2. Fill in:
   - **Amount (UGX)** — required, must be greater than zero.
   - **Payment Date** — defaults to today.
   - **Payment Method** — choose **Cash**, **Bank Transfer**, or **Card**.
   - **Reference** — optional (e.g. a transaction ID).
   - **Notes** — optional.
3. Click **Record Payment** to save.

A receipt is generated automatically — you don't need to do anything extra for that.

## Checking an occupant's balance

Open the occupant's profile. The **Payment Summary** section shows three figures:
- **Amount Due** — the total they're expected to pay.
- **Total Paid** — how much they've paid so far.
- **Outstanding** — what's left to pay (shown in red if there's a balance owing).

## Viewing or printing a receipt

Receipts are found on the dedicated **Receipts** page (in the left-hand menu) — not on the occupant's own
profile page.

1. Go to **Receipts**.
2. Use the search box to search by receipt number, occupant name, or payment reference, and/or filter by
   date range.
3. Click **PDF** next to the receipt you want — it opens as a PDF in a new browser tab, which you can print
   or save from there.

## Finding an occupant

Go to the **Occupants** page and type into the search box (placeholder text: **"Search by name, phone,
ID..."**). You can search by:
- First name
- Last name
- Phone number
- Student ID
- National ID

**Note:** you cannot search by email address — only the fields above are searched. If you type more than
one word (like a first and last name together), every word needs to match somewhere in those fields.

You can also filter the list by **All**, **Active**, or **Archived** using the tabs at the top.

## Checking available accommodation

Use **Property Explorer** for this (not the plain "Properties" page — that page only shows a summary
table, not availability).

1. Go to **Property Explorer** in the menu.
2. Click a property to expand it and see its sections.
3. Click a section to see its units.
4. Each unit is color-coded:
   - 🟢 **Green ("Available")** — under 75% occupied.
   - 🟡 **Yellow ("Nearly Full")** — 75% or more occupied.
   - 🔴 **Red ("Full")** — completely full, cannot accept new occupants.
5. Click a unit to open its details on the right-hand side (or as a pop-up on a phone/small screen), showing
   capacity, pricing, current occupants, and quick actions like **Assign Occupant** and **Record Payment**.

You can also search directly for a unit or occupant using the search box at the top of the Explorer page.

## Using Property Explorer for day-to-day work

Beyond just checking availability, the unit detail panel is a convenient shortcut for common tasks:
- See exactly who is currently staying in a unit, and whether they owe money (shown as a red balance badge
  next to their name).
- Click **View Occupant** to jump straight to their profile.
- Click **Record Payment** directly from there if they owe money.
- Click **Assign Occupant** if the unit has space, to jump straight into the assignment wizard for that
  specific unit.

## Basic administration (Property Manager and above)

Go to the **Administration** page. Depending on your role, you'll see up to four tabs:

- **Properties** — add a new property (Name and Code are required; Address and Description are optional),
  or edit/archive an existing one.
- **Sections** — pick a property, then add/edit/archive its sections. You can also reorder sections using
  the **Reorder** button.
- **Units** — pick a property and section, then add/edit/archive units. Each unit has a status: **Active**,
  **Maintenance**, or **Archived**.
- **Pricing** — pick a property, section, and unit, then set semester or monthly pricing rules with an
  effective date. A note on the page explains that changing a price doesn't retroactively affect occupants
  already assigned at the old price.

If you don't see a **Users** or **Audit Log** tab, that's expected — those are restricted to Super
Administrators only, since they involve managing other people's accounts.

## What to do if something appears wrong

KarosL tells you about problems in a few different ways:

- **A small colored box in the corner of the screen (a "toast")** — green means success, red means
  something went wrong, yellow is a warning, and blue is general information. These disappear on their own
  after a few seconds.
- **A red message under a specific field** — this means that one field needs fixing before you can submit
  the form (e.g. "Enter a valid amount greater than 0.").
- **A red box above the Save/Submit button** — this is a more general error message, usually meaning the
  whole action couldn't be completed (for example, if you try to do something your role isn't allowed to do,
  you may see a message like "You do not have permission to perform this action.").
- **You're suddenly sent back to the login page** — this means your session has expired (for security,
  logins don't last forever). Just log back in and continue where you left off.
- **A full-page message saying "Something went wrong"** — this is rare and means something unexpected
  happened. You'll see two buttons: **Try Again** and **Go to Overview**. Try clicking **Try Again** first.

**If an error message doesn't make sense, or keeps happening after you've tried again:** write down exactly
what the message said and what you were doing when it appeared, then contact your system administrator.
KarosL doesn't have a built-in help or support chat — any technical issue should go to whoever manages the
system for your organization.

**Never share your username or password with anyone**, including in a support request — nobody should ever
need your password to help you.
