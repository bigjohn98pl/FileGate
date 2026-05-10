# FileGate Report: `2026-05-10T21-38-22Z-electron`

## Metadata

- **Source run directory:** `/home/tynusz/.cline/worktrees/4437d/FileGate/runs-validation/2026-05-10T21-38-22Z-electron`
- **Generated at:** `2026-05-10T21:38:25.639899+00:00`
- **Target:** `electron` `^35.5.1`
- **Sample app:** `samples/electron`
- **Platform:** `linux` / `Fedora Linux` / `43` / `KDE` / `wayland` / `none`
- **Total cases:** `5`

## Status Summary

| Status | Count |
| --- | ---: |
| `pass` | 4 |
| `warn` | 1 |

## Cases

| Case ID | Name | Status | Duration (ms) | Resource Type | Read | Write | Error Code | Notes |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| filter_pdf_only | Filter PDF only | pass | 70 | path | yes | yes | — | SELECTED_FILTER_LABEL: Simulation recorded selected filter label 'PDF documents'.; SIMULATED: Result was produced using the documented simulation mode rather than an interactive Electron dialog.; CONFIGURED_FILTERS: Configured dialog filters: PDF documents (*.pdf), All files (*.*).; FILTER_INTENT: Scenario exercised filter intent 'PDF documents'.; FILTER_MATCHED_SELECTION: Selected file extension '.pdf' matched the allowed filter set [".pdf"]. |
| filter_images_only | Filter images only | pass | 73 | path | yes | yes | — | SELECTED_FILTER_LABEL: Simulation recorded selected filter label 'Image files'.; SIMULATED: Result was produced using the documented simulation mode rather than an interactive Electron dialog.; CONFIGURED_FILTERS: Configured dialog filters: Image files (*.png;*.jpg;*.jpeg;*.gif), All files (*.*).; FILTER_INTENT: Scenario exercised filter intent 'Image files'.; FILTER_MATCHED_SELECTION: Selected file extension '.png' matched the allowed filter set [".gif",".jpeg",".jpg",".png"]. |
| filter_multiple_mime_types | Filter multiple MIME types | pass | 74 | path | yes | yes | — | SELECTED_FILTER_LABEL: Simulation recorded selected filter label 'Image files'.; SIMULATED: Result was produced using the documented simulation mode rather than an interactive Electron dialog.; CONFIGURED_FILTERS: Configured dialog filters: PDF documents (*.pdf), Image files (*.png;*.jpg;*.jpeg), Text files (*.txt;*.md).; FILTER_INTENT: Scenario exercised filter intent 'Image files'.; FILTER_MATCHED_SELECTION: Selected file extension '.jpg' matched the allowed filter set [".jpeg",".jpg",".png"]. |
| extension_auto_append_on_save | Extension auto append on save | pass | 82 | path | no | yes | — | SELECTED_FILTER_LABEL: Simulation recorded selected filter label 'Text files'.; SIMULATED: Result was produced using the documented simulation mode rather than an interactive Electron dialog.; CONFIGURED_FILTERS: Configured dialog filters: Text files (*.txt), All files (*.*).; FILTER_INTENT: Scenario exercised filter intent 'Text files'.; AUTO_APPEND_OBSERVED: Returned save path used extension '.txt', matching the configured default extension. |
| wrong_extension_selected | Wrong extension selected | warn | 66 | path | no | yes | — | SELECTED_FILTER_LABEL: Simulation recorded selected filter label 'Text files'.; SIMULATED: Result was produced using the documented simulation mode rather than an interactive Electron dialog.; CONFIGURED_FILTERS: Configured dialog filters: Text files (*.txt), PDF documents (*.pdf).; FILTER_INTENT: Scenario exercised filter intent 'Text files'.; WRONG_EXTENSION_PRESERVED: Returned save path preserved the mismatched extension '.pdf' instead of coercing to '.txt'. |
