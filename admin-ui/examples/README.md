# Admin UI Widget - Examples

This directory contains example applications demonstrating how to use the `<admin-ui-widget>` web component in different frameworks.

## Prerequisites

Before running any example, you must first build the web component:

```bash
# From the admin-ui directory
cd ..
npm install
npm run build:wc
```

This creates the `dist-wc/` directory with the bundled web component.

---

## Examples

### 1. Vanilla HTML (Simplest)

A pure HTML/JavaScript example with no build step required.

**Run it:**
```bash
# Option A: Open directly in browser
open vanilla-html/index.html

# Option B: Use any static server
npx serve vanilla-html
# Then open http://localhost:3000
```

**Key points:**
- Uses UMD bundle directly via `<script>` tag
- Demonstrates all attributes and events
- No framework dependencies

---

### 2. React 18 Host

A React 18 application demonstrating integration with an older React version (the widget uses React 19 internally).

**Run it:**
```bash
cd react-host
npm install
npm run dev
# Open http://localhost:3001
```

**Key points:**
- React 18 host + React 19 widget (isolated via Shadow DOM)
- TypeScript with proper type definitions
- Event handling with `useRef` and `useEffect`
- Demonstrates programmatic control

---

### 3. Angular 17 Host

An Angular 17 application using the widget as a custom element.

**Run it:**
```bash
cd angular-host
npm install
npm start
# Open http://localhost:4200
```

**Key points:**
- Uses `CUSTOM_ELEMENTS_SCHEMA` for custom element support
- Attribute binding with `[attr.api-base-url]` syntax
- Event handling with Angular's lifecycle hooks
- Standalone component architecture

---

## Common Patterns

### Loading the Widget

**UMD (Script tag - works everywhere):**
```html
<script src="path/to/admin-ui-widget.umd.js"></script>
```

**ESM (Modern bundlers):**
```javascript
import '@common/context-management-widget'
```

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `api-base-url` | string | `''` | Backend API base URL |
| `tenant-id` | string | `'default'` | Tenant identifier |
| `initial-route` | string | `'/'` | Starting page |
| `theme` | `'light' \| 'dark' \| 'system'` | `'system'` | Color theme |

### Events

```javascript
const widget = document.querySelector('admin-ui-widget');

widget.addEventListener('ready', (e) => {
  console.log('Widget initialized');
});

widget.addEventListener('faq-created', (e) => {
  console.log('FAQ created:', e.detail);
});

widget.addEventListener('error', (e) => {
  console.error('Widget error:', e.detail.message);
});
```

### Methods

```javascript
// Navigate to a route
widget.navigate('/graph');

// Refresh the widget
widget.refresh();

// Change theme programmatically
widget.setTheme('dark');
```

---

## Troubleshooting

### Widget not rendering

1. Check that `dist-wc/` exists (run `npm run build:wc` from parent directory)
2. Verify the script path is correct
3. Check browser console for errors

### Styles look wrong

- The widget uses Shadow DOM for style isolation
- Host app styles should not affect the widget
- If using custom fonts (Inter, JetBrains Mono), ensure they're loaded

### Events not firing

- Events use `composed: true` to cross Shadow DOM boundary
- Make sure listeners are attached before the widget emits events
- Use `ready` event to know when widget is initialized

### React: "Unknown element" warnings

Add type declarations:
```typescript
declare global {
  namespace JSX {
    interface IntrinsicElements {
      'admin-ui-widget': React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          'api-base-url'?: string
          'tenant-id'?: string
          'initial-route'?: string
          theme?: string
        },
        HTMLElement
      >
    }
  }
}
```

### Angular: Can't bind to 'api-base-url'

Use attribute binding syntax:
```html
<!-- Wrong -->
<admin-ui-widget [api-base-url]="url"></admin-ui-widget>

<!-- Correct -->
<admin-ui-widget [attr.api-base-url]="url"></admin-ui-widget>
```

And add `CUSTOM_ELEMENTS_SCHEMA` to your component or module.
