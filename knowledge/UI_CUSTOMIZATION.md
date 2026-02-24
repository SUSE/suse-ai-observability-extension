# SUSE Observability UI Customization Guide Summary

This document summarizes key patterns for customizing the SUSE Observability UI, based on official guides.

## 1. Menu Structure
- **MainMenuGroup**: Container for menu items.
  - `_type: MainMenuGroup`
  - `id`: Negative integer.
  - `identifier`: URN.
  - `items`: List of `MainMenuViewItem` linking to `QueryView` identifiers.
- **QueryView**: Defines data and visualization for a menu item.
  - `query`: STQL statement.
  - `viewType`: URN of the `ViewType` defining columns/layout.

## 2. Overview Page (Tables)
- **ViewType**: Defines columns, filters, and flags.
- **Column Types**:
  - `ViewTypeTableColHealth`: Visual health indicator.
  - `ViewTypeTableColName`: Primary name.
  - `ViewTypeTableColText`: Property-based text.
  - `ViewTypeTableColNumber`: Numeric data with unit formatting.
  - `ViewTypeTableColDuration`: Time-based durations (e.g., Age).
  - `ViewTypeTableColComponentLink`: Link to related components.
  - `ViewTypeTableColMetricBinding`: Binds a `MetricBinding` to a column.
  - `ViewTypeTableColPromql`: Direct PromQL query results.

## 3. Highlight Page (Component Details)
- **Highlights**: Property under `ComponentType`.
  - **Fields**: Individual data points in "About".
    - `valueExtractor`: `PropertySource`, `TagsSource`, `HealthSource`, `CompositeSource`.
    - `display`: `TextDisplay`, `TagDisplay`, `HealthBadgeDisplay`, `ComponentLinkDisplay`.
  - **Metrics**: Categories of metric bindings.
  - **Related Resources**: STQL-based links to neighbors.
  - **Events/Logs**: Configuration for historical data visibility.

## 4. Component Data Mapping
- UI customization relies on component `properties` and `labels`.
- Identifiers are critical for linking health (Monitors) and metrics (MetricBindings).
- `COMPONENT_ID` and `COMPONENT_NAME` are usable placeholders in STQL/templates.
