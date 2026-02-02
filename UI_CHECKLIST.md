# UI Visual Checklist (Quick)

Use this after UI changes to quickly verify nothing broke.

## Core pages

- `Login`: `/`
  - Form inputs readable on dark background
  - Flash messages visible and auto-dismiss

- `User Dashboard`: `/user/dashboard`
  - Navbar links work (Home, Summary, Profile, Logout)
  - Parking lot cards align and wrap on small screens
  - Bookings table readable

- `Summary`: `/user/summary`
  - Chart loads (or shows “No data yet”)
  - No console errors

- `Release`: `/user/release/<booking_id>`
  - Cost breakdown readable

## Admin pages

- `Admin Dashboard`: `/admin/dashboard`
  - Spot bubbles align; first 10 + remaining counter
  - Edit/Delete actions visible

- `Admin Search`: `/admin/search`
  - Search controls aligned
  - Results cards wrap with spot grid

- `Admin Users`: `/admin/admin/users`
  - User cards wrap correctly

## Responsive checks

- Narrow viewport (~375px)
  - Navbar doesn’t overflow badly (links wrap or remain usable)
  - Forms become single-column (where applicable)

## Accessibility quick checks

- Tab through inputs/links
  - Focus ring visible on inputs/buttons/nav links

