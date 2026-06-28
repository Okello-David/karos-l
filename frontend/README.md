# KarosL — Frontend

Accommodation management platform frontend built with React 19, Vite 8, Tailwind CSS 3, and React Router 7.

## Architecture

```
src/
├── App.jsx                  # Root component with route definitions
├── main.jsx                 # Application entry point
├── index.css                # Tailwind imports + base styles
├── layouts/
│   └── MainLayout.jsx       # Responsive shell: sidebar + topbar + content
├── components/
│   ├── Sidebar.jsx          # Desktop/mobile navigation sidebar
│   ├── Topbar.jsx           # Top bar with page title + breadcrumb
│   ├── PageContainer.jsx    # Page wrapper with title + description
│   ├── Card.jsx             # Content card container
│   ├── Button.jsx           # Reusable button (primary/secondary/ghost)
│   ├── EmptyState.jsx       # Empty state placeholder
│   ├── Breadcrumb.jsx       # Breadcrumb navigation
│   └── dashboard/
│       ├── StatisticCard.jsx        # Large metric with value + action
│       ├── ActionCard.jsx           # Quick action button list
│       ├── ActivityCard.jsx         # Timeline-style activity feed
│       ├── PaymentTable.jsx         # Recent payments table
│       └── PropertySummaryCard.jsx  # Property card with occupancy bar
├── pages/
│   ├── Dashboard.jsx        # Overview / dashboard with mock data
│   ├── Properties.jsx       # Property management
│   ├── Occupants.jsx        # Occupant management
│   ├── Payments.jsx         # Payment tracking
│   ├── Reports.jsx          # Reporting
│   ├── Administration.jsx   # System administration
│   └── NotFound.jsx         # 404 page
├── data/
│   └── mockDashboard.js     # Realistic mock data for dashboard
├── hooks/                   # Custom React hooks (ready)
├── services/                # API client code (ready)
└── utils/
    └── format.js            # Currency formatting (UGX)
```

## Layout

| Breakpoint | Navigation | Top Bar | Content |
|-----------|-----------|---------|---------|
| Desktop (lg+) | Left sidebar (fixed, w-64) | Sticky top bar with breadcrumb | Scrollable main area |
| Tablet/Mobile | Slide-out drawer (hamburger) | App bar with menu button | Full-width content |

## Dashboard

The Overview dashboard (`/`) presents 6 sections that help managers prioritize decisions:

| Section | Component | Purpose |
|---------|-----------|---------|
| Occupancy Summary | `StatisticCard` | Occupied/available beds at a glance |
| Outstanding Payments | `StatisticCard` | Number owing + total balance |
| Properties Overview | `PropertySummaryCard` (×3) | Per-property occupancy bar |
| Recent Payments | `PaymentTable` | Latest 5 payments with amounts |
| Quick Actions | `ActionCard` | One-click: register, record, view, report |
| Recent Activity | `ActivityCard` | Timeline of check-ins, check-outs, payments |

Grid layout: 1 col (mobile) → 2 col (tablet) → 3 col (desktop). Mock data in `src/data/mockDashboard.js` matches the backend domain model. No API connection — replace `import` from mock data with real API calls when ready.

## Design Principles

- **Readability first** — generous spacing, large text, high contrast
- **Calm and uncluttered** — minimal visual noise, consistent spacing
- **Professional** — clean typography (Inter), soft blue primary palette
- **Accessible** — semantic HTML, keyboard navigation, ARIA labels

## Routing

| Path | Page | Nav Label |
|------|------|-----------|
| `/` | Dashboard | Overview |
| `/properties` | Properties | Properties |
| `/occupants` | Occupants | Occupants |
| `/payments` | Payments | Payments |
| `/reports` | Reports | Reports |
| `/administration` | Administration | Administration |
| `*` | NotFound | — |

## Commands

```bash
npm run dev       # Start development server (Vite)
npm run build     # Production build
npm run lint      # Run Oxlint
npm run preview   # Preview production build
```
