# Test Cases

## Purpose

Define the canonical case catalog and execution model for FileGate conformance testing.

## Automation Levels

- `automatic`: no user interaction.
- `semi_automatic`: user action required in native/system dialog.
- `manual`: checklist-based human validation.

## Case Definition Template

Each case definition should include:

- `case_id`
- `name`
- `automation_level`
- `objective`
- `preconditions`
- `steps`
- `expected_result`
- `artifacts`

## MVP Core Case Set

### Dialog Basics

- `open_file_single`
- `open_file_multiple`
- `open_folder`
- `save_file_new`
- `save_file_overwrite`
- `cancel_open_dialog`
- `cancel_save_dialog`

### Path and Naming

- `path_with_spaces`
- `unicode_filename`
- `polish_characters_filename`
- `very_long_filename`
- `nested_directory_path`
- `relative_vs_absolute_path`
- `case_sensitive_collision`

### File Types and Filters

- `filter_pdf_only`
- `filter_images_only`
- `filter_multiple_mime_types`
- `extension_auto_append_on_save`
- `wrong_extension_selected`

### Permissions

- `read_only_file`
- `write_to_read_only_file`
- `permission_denied_file`
- `permission_denied_directory`
- `execute_permission_irrelevant`

### Sandbox and Portals

- `flatpak_open_file_portal`
- `flatpak_save_file_portal`
- `xdg_document_portal_persistence`
- `portal_cancel_behavior`
- `portal_returns_uri_or_path`
- `sandbox_no_home_access_without_grant`

### Symlink and Mount Cases

- `symlink_to_file`
- `symlink_to_directory`
- `broken_symlink`
- `external_drive_path`
- `network_share_path`

### Stability and Regression

- `open_dialog_multiple_times`
- `open_after_app_restart`
- `persistent_access_after_restart`
- `revoked_access_behavior`
- `timeout_when_dialog_not_closed`

## Case Prioritization for MVP

Priority order:

1. Dialog basics
2. Path/naming reliability
3. Permission behavior
4. Sandbox/portal behavior
5. Stability and persistence
