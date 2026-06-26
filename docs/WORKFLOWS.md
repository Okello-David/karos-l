# Workflows & User Journeys

## Primary User Persona

An elderly hostel owner with limited technical experience. The interface must prioritize simplicity, large touch targets, visual navigation, and clear feedback for every action.

---

## 1. Registering a New Property

| Aspect | Detail |
|---|---|
| **Starting screen** | Dashboard home — large **+ New Property** card/button centered at top |
| **User actions** | 1. Taps "New Property" → inline form slides down or modal opens. 2. Enters *Property Name* only (required). 3. Optionally enters *Address* (large textarea, hint: "Street, city"). 4. Taps green **Save** button. |
| **System actions** | Creates Property with `is_active = true`. Shows a brief "Property saved!" toast with visual feedback. The property card now appears on the Dashboard. |
| **Validation** | Property Name required (min 2 chars). Duplicate name detected → "A property with this name already exists — please use a different name." |
| **Possible errors** | Network timeout → "Could not save. Check your connection and try again." |
| **Completion state** | Dashboard shows the new property as a card. Tapping the card enters that property's management screen. |

---

## 2. Adding Sections

| Aspect | Detail |
|---|---|
| **Starting screen** | Inside a property, the default tab is **Sections**. A prominent **+ Add Section** button sits at the bottom. |
| **User actions** | 1. Taps "+ Add Section". 2. Types a short name (e.g. "Block A", "Floor 1"). 3. Taps "Save". |
| **System actions** | Creates Section under current property. Section card appears immediately. User stays on the same screen. |
| **Validation** | Section name required. Duplicate names within the same property rejected → "You already have a section called that in this property." |
| **Possible errors** | Saving to wrong property → mitigated by showing the current property name in the header at all times. |
| **Completion state** | List of section cards visible. Each card shows the section name and a unit count (e.g. "0 units"). |

---

## 3. Adding Accommodation Units

| Aspect | Detail |
|---|---|
| **Starting screen** | Inside a section, the **Units** tab is active. A big **+ Add Unit** button. |
| **User actions** | 1. Taps "+ Add Unit". 2. Enters *Unit name* (e.g. "Room 101"). 3. Sets *Capacity* — a stepper control (+/−) with large labels "Number of beds: 2". 4. Enters *Semester price* (large currency input). 5. Enters *Monthly price* (large currency input). 6. Taps "Save". |
| **System actions** | Creates Unit. Returns to unit list. New unit card shows name, capacity, and both prices in a clean format. |
| **Validation** | All fields required. Capacity min 1. Prices must be positive numbers. If both prices are entered and the monthly × 4 is much less than the semester price, a gentle non-blocking warning appears: "The monthly price × 4 is much less than the semester price. Is this correct?" |
| **Possible errors** | User enters letters in a price field → input mask prevents it (numeric keyboard on mobile). |
| **Completion state** | Unit card visible in the section's unit list with an occupancy indicator (e.g. "0 / 2 occupants"). |

---

## 4. Registering a New Student

| Aspect | Detail |
|---|---|
| **Starting screen** | **Students** tab in the sidebar. A **+ Register Student** button at top. |
| **User actions** | 1. Taps "+ Register Student". 2. Enters *First name* and *Last name*. 3. Enters *Phone number* (optional — hint: "For SMS reminders"). 4. Enters *Student ID* (optional — "School/exam number"). 5. Taps "Save". |
| **System actions** | Creates Student record. If the owner has just registered the student but has not yet assigned a unit, a prompt appears: "Do you want to assign this student to a unit now?" with two large buttons: **Yes, assign now** / **No, later**. |
| **Validation** | First and last name required. Duplicate email → warning but not blocking (some students share emails with parents). Phone number format validated but not required. |
| **Possible errors** | Saving a duplicate student → "This student may already be registered. Check the list before adding again." |
| **Completion state** | Student appears in the student list with a status badge: "Unassigned". If the owner chose to assign, they transition to the Assign workflow. |

---

## 5. Assigning a Student to a Unit

| Aspect | Detail |
|---|---|
| **Starting screen** | Two possible entry points: (a) from the "Register Student" prompt, or (b) from the student's detail card via an **Assign Unit** button. |
| **User actions** | 1. System shows a 3-step visual wizard. **Step 1**: "Which property?" — tap a property card. **Step 2**: "Which section?" — tap a section card. **Step 3**: "Which unit?" — tap a unit card (available units highlighted green; full units grayed out with "Full" badge). 2. Owner taps **Confirm Assignment**. |
| **System actions** | Creates Occupancy with `start_date = today`, `end_date = NULL`, `billing_mode = 'semester'` (default). Student status changes to "Active". Unit occupancy count increments. |
| **Validation** | Unit must have capacity available. If capacity reached, the unit is non-tappable (grayed). Student must not already have an active occupancy — if they do, the system shows "This student is already assigned to [unit name]. Move them first?" with a button to go to the Move workflow. |
| **Possible errors** | Two owners assign the same last-available unit simultaneously → handled at DB level with optimistic locking; the second owner sees "That unit was just taken. Please choose another." |
| **Completion state** | Success screen showing "Student assigned to [unit name]!" with a summary card (student name, unit, start date, billing mode). A **Make Payment** button is offered. |

---

## 6. Recording a Payment

| Aspect | Detail |
|---|---|
| **Starting screen** | From any screen with a student's name visible, a **Record Payment** button is present. Also accessible from the Payments tab. |
| **User actions** | 1. Student name is pre-filled. Owner confirms it is the right student (shows photo + name + current unit). 2. Enters *Amount* — large numeric input with a calculator-style keypad on mobile. 3. Selects *Payment method* — three large icon buttons: Cash, Bank Transfer, Card. 4. Optionally adds *Note* (e.g. "First installment"). 5. Optionally enters *Reference number* (for transfers). 6. Taps **Record Payment**. |
| **System actions** | Creates Payment record. Immediately recalculates and displays the student's new balance: "Outstanding balance: ₱2,500". Shows a confirmation card with receipt details. Offers two actions: "Print Receipt" / "Record Another Payment". |
| **Validation** | Amount must be > 0. Owner can record a payment higher than the balance — system accepts it and shows a positive balance as "Credit: ₱500". |
| **Possible errors** | Double payment (same reference entered twice) → "A payment with this reference was already recorded on [date]. Is this a duplicate?" |
| **Completion state** | Payment receipt card displayed. Student balance updated everywhere. Recent payment shown in student's history. |

---

## 7. Moving a Student to Another Unit

| Aspect | Detail |
|---|---|
| **Starting screen** | Student's detail card. A **Move to Another Unit** button (icon and label "Move Room"). |
| **User actions** | 1. Taps "Move Room". 2. System shows current unit info (name, section, property) with a "From" label. 3. Owner selects new unit using the same visual 3-step wizard (Property → Section → Unit). Available units highlighted green. 4. Owner confirms by tapping **Complete Move**. |
| **System actions** | Closes current Occupancy: sets `end_date = yesterday`. Creates new Occupancy: `start_date = today`, `end_date = NULL`, `billing_mode = 'monthly'` (default — mid-period moves typically switch to monthly proration). |
| **Validation** | Target unit must have capacity. Student must have an active occupancy. If the move is within the same section, a soft confirmation appears: "This is in the same section. Are you sure?" |
| **Possible errors** | Student has outstanding balance → warning: "This student has an unpaid balance of ₱X. Record a payment before or after the move?" (non-blocking). |
| **Completion state** | Success screen: "Move completed! [Name] is now in [New Unit] since today." A timeline of the student's occupancy history shows the old and new entries. |

---

## 8. Checking Out a Student

| Aspect | Detail |
|---|---|
| **Starting screen** | Student's detail card. A **Check Out** button (red, bottom of card, requires confirmation). |
| **User actions** | 1. Taps "Check Out". 2. System shows a confirmation dialog: "Check out [Name] from [Unit]? They will vacate the unit." 3. Two large buttons: **Confirm Check-out** / **Cancel**. 4. If confirmed, owner is asked "Was there an outstanding balance?" with buttons: **Yes — Record Payment** / **No, balance is settled** / **Remind Later**. 5. If "Remind Later" is chosen, the student appears on the Outstanding Balances list automatically. |
| **System actions** | Sets `end_date = today` on the active Occupancy. Calculates final balance. If balance > 0 and owner chose "Remind Later", marks the student for the Outstanding Balances list. The unit's available capacity increases by 1. |
| **Validation** | Student must have an active occupancy. If not: "This student is not currently assigned to any unit." |
| **Possible errors** | Checking out the wrong student → the 2-step confirmation (dialog + balance decision) prevents accidental check-outs. |
| **Completion state** | Student status changes to "Former". Unit occupancy decremented. Student still visible in the student list with a "Former" filter. The owner sees "[Name] checked out successfully from [Unit]." |

---

## 9. Viewing Occupancy

| Aspect | Detail |
|---|---|
| **Starting screen** | Dashboard has a large **Occupancy Overview** card/widget. Also accessible via the **Occupancy** tab. |
| **User actions** | 1. By default, shows current occupancy: a tree view (Property → Section → Unit → student names). 2. Owner can toggle between two views: **By Unit** (default) and **By Student**. 3. **By Unit**: expandable cards. Tapping a unit shows occupant photos/names. 4. **By Student**: alphabetical list of active students with their unit. 5. Filter buttons at top: "All", "Available Units Only", "Full Units Only". 6. Tapping a student or unit navigates to its detail page. |
| **System actions** | Reads `Occupancy WHERE end_date IS NULL`. Groups results by Property → Section → Unit. For each unit, displays `current_occupants / capacity`. |
| **Validation** | N/A — read-only view. |
| **Possible errors** | None. |
| **Completion state** | Owner sees a clear visual map of the entire accommodation. Empty units are visibly marked "Available" with a green indicator. |

---

## 10. Finding Students with Outstanding Balances

| Aspect | Detail |
|---|---|
| **Starting screen** | Dashboard widget titled **Outstanding Balances** showing a count (e.g. "3 students owe payments"). Tapping it opens the full list. Also accessible from the **Payments** tab via a "View Debtors" button. |
| **User actions** | 1. A list of students is shown, sorted by debt amount (highest first). 2. Each row shows: student name, unit, amount owed, days overdue. 3. Owner can tap a student to see their balance breakdown. 4. A **Record Payment** button is on each row. 5. Filter button: "All", "Over 30 Days", "Over 60 Days". |
| **System actions** | For each student with an active (or recently ended) occupancy, computes `SUM(charge) - SUM(payment)` as the balance. Lists only positive balances (debtors). Charge calculation uses the billing formula defined in the database architecture. |
| **Validation** | N/A. |
| **Possible errors** | If a unit's price was changed mid-period, the calculated charge may be off. This is a schema limitation noted in DATABASE.md (mitigated by a future `UnitPriceHistory` table). |
| **Completion state** | The owner can see who owes money at a glance and tap to collect payment in 2 taps. |

---

## 11. Viewing Payment History

| Aspect | Detail |
|---|---|
| **Starting screen** | Student's detail card → a **Payments** tab/section showing a list. Also available from the Payments tab with a student filter. |
| **User actions** | 1. By default, shows all payments for a selected student, most recent first. 2. Each row: date, amount, method, reference (if any), running balance. 3. Owner can switch to **All Students** view: a paginated list of every recorded payment, filterable by date range and method. 4. Tap any payment to see the full receipt in a printable format. |
| **System actions** | Queries `Payment WHERE student_id = X ORDER BY payment_date DESC`. For each row, optionally computes a running total. |
| **Validation** | N/A. |
| **Possible errors** | None. |
| **Completion state** | Transparent audit trail of all money received. |

---

## 12. Renaming a Unit

| Aspect | Detail |
|---|---|
| **Starting screen** | Unit's detail card. An **Edit** button (pencil icon) in the top-right corner of the card. |
| **User actions** | 1. Taps the Edit button. 2. The unit name becomes an editable text field (inline edit). 3. Owner modifies the name (e.g. "Room 101-A" → "Room 101-B"). 4. Taps **Save** (or presses Enter). 5. A confirmation toast appears: "Unit renamed!" |
| **System actions** | Updates `Unit.name`. No other table is affected. Occupancy records reference `unit_id`, not the name string, so history remains intact. |
| **Validation** | Name must be unique within the section. If duplicate: "Another unit in this section already has that name." |
| **Possible errors** | None significant. |
| **Completion state** | Unit displays the new name everywhere: occupancy view, student cards, reports. |

---

## 13. Viewing Reports

| Aspect | Detail |
|---|---|
| **Starting screen** | **Reports** tab (last item in the sidebar). |
| **User actions** | 1. Owner sees a grid of report card options: **Occupancy Rate**, **Revenue Summary**, **Outstanding Debts**, **Student Movements**, **Payment Methods Breakdown**. 2. Taps any card. 3. For date-based reports, a simple date range selector appears: two large calendar inputs "From" and "To" (default: this semester). 4. Report renders as a large card with a big number (e.g. "78% Occupied") and a simple bar chart. 5. Owner can tap **Print** to get a printer-friendly version. |
| **System actions** | Aggregates data based on the report type. Returns computed statistics. Charts use simple inline SVG (no extra charting library needed for MVP). |
| **Validation** | Date range: From must be before To. |
| **Possible errors** | No data for the selected period → "No data available for this period. Try a wider date range." |
| **Completion state** | Owner sees actionable numbers. Reports are generated instantly (no loading spinners for small datasets). |

---

## Navigation Structure

### Sidebar (Desktop)

```
┌─────────────────────────────────┐
│         KAROSL                   │
│  (property name when inside)     │
├─────────────────────────────────┤
│                                 │
│  [🏠]  Dashboard                 │
│  [🏢]  Properties                │
│  [👤]  Students                  │
│  [💰]  Payments                  │
│  [📋]  Occupancy                 │
│  [📊]  Reports                   │
│  [⚙️]  Settings                  │
│                                 │
└─────────────────────────────────┘
```

### Navigation Rules

- Every page title is a large, bold header with a breadcrumb below (e.g. "Properties → Block A → Room 101").
- The current property name is always visible in the top bar when inside a property's context.
- A persistent **+** (Add) button in the bottom-right corner adds whatever is contextually relevant (student, payment, unit) based on the current page.
- No hamburger menu on desktop — the sidebar is always visible.
- On mobile, the sidebar collapses into a bottom tab bar (see Mobile layout).

---

## Dashboard Layout

### Desktop Browser

```
┌─────────────────────────────────────────────────────────────┐
│ 🏠 KarosL                            [Property: All] [⚙️]  │
├──────────┬──────────────────────────────────────────────────┤
│          │  ┌──────────────────────────────────────────────┐│
│ Sidebar  │  │    Good morning, [Name]                      ││
│          │  │    You have 3 students with overdue payments  ││
│          │  └──────────────────────────────────────────────┘│
│          │                                                  │
│          │  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│          │  │ 45 / 60  │ │  ₱128K   │ │  3 Overdue│         │
│          │  │ Occupied │ │ Revenue  │ │ Payments  │         │
│          │  └──────────┘ └──────────┘ └──────────┘         │
│          │                                                  │
│          │  ┌──────────────────────────────────────────────┐│
│          │  │  Recent Activity                             ││
│          │  │  ● John paid ₱5,000 — 2 hours ago           ││
│          │  │  ● Maria moved to Room 204 — yesterday       ││
│          │  │  ● New student: Alex Reyes — 2 days ago      ││
│          │  └──────────────────────────────────────────────┘│
│          │                                                  │
│          │  ┌──────────────────────────────────────────────┐│
│          │  │  Occupancy by Property                       ││
│          │  │  [████████████████░░░░] 80% — Main Building ││
│          │  │  [██████████░░░░░░░░░░] 50% — Annex         ││
│          │  └──────────────────────────────────────────────┘│
└──────────┴──────────────────────────────────────────────────┘
```

### Mobile Phone

```
┌─────────────────────┐
│ ☰ KarosL       [⚙️] │
├─────────────────────┤
│                     │
│ Good morning!       │
│                     │
│ ┌─────────────────┐│
│ │  45 / 60        ││
│ │  Units Occupied ││
│ └─────────────────┘│
│                     │
│ ┌─────────────────┐│
│ │  ₱128,500       ││
│ │  Revenue (MTD)  ││
│ └─────────────────┘│
│                     │
│ ┌─────────────────┐│
│ │  3 Overdue      ││
│ │  Payments       ││
│ └─────────────────┘│
│                     │
│  Recent Activity    │
│  ─────────────────  │
│  John paid ₱5,000  │
│  Maria moved...     │
│  New: Alex Reyes    │
│                     │
│                     │
├─────────────────────┤
│ 🏠  👤  💰  📋  📊 │
└─────────────────────┘
```

**Mobile bottom tab bar** (always visible, 5 icons):
- **🏠** Dashboard
- **👤** Students / People
- **💰** Payments
- **📋** Occupancy
- **📊** Reports

Properties and Settings move into a drawer accessible from the ☰ hamburger icon in the top bar. The **+** FAB (floating action button) sits above the tab bar for quick adds.

---

## Key UX Principles

| Principle | Implementation |
|---|---|
| **Progressive disclosure** | 3-step wizards for complex tasks (assigning, moving) instead of one overwhelming form. |
| **Forgiveness** | Every destructive action has a 2-step confirmation. Check-out requires confirming the balance decision. |
| **Recognition over recall** | Students shown with names and photos/initials; units with visual occupancy bars. |
| **Consistency** | "+" button always adds something. Sidebar order never changes. |
| **Accessibility** | Large touch targets (min 48×48 px), high contrast text, icons paired with text labels. |
| **Feedback** | Every action produces a toast ("Saved!", "Moved!", "Payment recorded") and a visual state change. |
| **Error prevention** | Numeric-only inputs for prices; available units highlighted green, full units grayed out. |
