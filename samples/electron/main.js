const { app, BrowserWindow, dialog } = require("electron");
const fs = require("fs");
const os = require("os");
const path = require("path");

const SCHEMA_VERSION = "0.1";
const SAMPLE_APP_PATH = "samples/electron";
const TARGET_NAME = "electron";
const RESULT_STATUSES = new Set([
  "pass",
  "fail",
  "warn",
  "skip",
  "manual_required",
  "unsupported",
  "timeout",
  "blocked",
  "inconclusive",
]);

const CASE_DEFAULTS = {
  open_file_single: { name: "Open file single", automation_level: "semi_automatic", dialog_type: "open_file" },
  open_file_multiple: { name: "Open file multiple", automation_level: "semi_automatic", dialog_type: "open_files" },
  open_folder: { name: "Open folder", automation_level: "semi_automatic", dialog_type: "open_folder" },
  save_file_new: { name: "Save file new", automation_level: "semi_automatic", dialog_type: "save_file" },
  filter_pdf_only: { name: "Filter PDF only", automation_level: "semi_automatic", dialog_type: "open_file" },
  filter_images_only: { name: "Filter images only", automation_level: "semi_automatic", dialog_type: "open_file" },
  filter_multiple_mime_types: { name: "Filter multiple MIME types", automation_level: "semi_automatic", dialog_type: "open_file" },
  extension_auto_append_on_save: { name: "Extension auto append on save", automation_level: "semi_automatic", dialog_type: "save_file" },
  wrong_extension_selected: { name: "Wrong extension selected", automation_level: "semi_automatic", dialog_type: "save_file" },
  save_file_overwrite: { name: "Save file overwrite", automation_level: "semi_automatic", dialog_type: "save_file" },
  path_with_spaces: { name: "Path with spaces", automation_level: "semi_automatic", dialog_type: "open_file" },
  unicode_filename: { name: "Unicode filename", automation_level: "semi_automatic", dialog_type: "open_file" },
  polish_characters_filename: { name: "Polish characters filename", automation_level: "semi_automatic", dialog_type: "open_file" },
  very_long_filename: { name: "Very long filename", automation_level: "semi_automatic", dialog_type: "open_file" },
  nested_directory_path: { name: "Nested directory path", automation_level: "semi_automatic", dialog_type: "open_file" },
  relative_vs_absolute_path: { name: "Relative vs absolute path", automation_level: "semi_automatic", dialog_type: "open_file" },
  case_sensitive_collision: { name: "Case sensitive collision", automation_level: "semi_automatic", dialog_type: "open_file" },
  cancel_open_dialog: { name: "Cancel open dialog", automation_level: "semi_automatic", dialog_type: "open_file", cancel_expected: true },
  cancel_save_dialog: { name: "Cancel save dialog", automation_level: "semi_automatic", dialog_type: "save_file", cancel_expected: true },
  open_dialog_multiple_times: { name: "Open dialog multiple times", automation_level: "semi_automatic", dialog_type: "open_file" },
  open_after_app_restart: { name: "Open after app restart", automation_level: "semi_automatic", dialog_type: "open_file" },
  persistent_access_after_restart: { name: "Persistent access after restart", automation_level: "semi_automatic", dialog_type: "open_file" },
  revoked_access_behavior: { name: "Revoked access behavior", automation_level: "manual", dialog_type: "open_file" },
  timeout_when_dialog_not_closed: { name: "Timeout when dialog not closed", automation_level: "semi_automatic", dialog_type: "open_file" },
};

function parseArgs(argv) {
  const args = { scenario: null, output: null };
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (current === "--scenario") {
      args.scenario = argv[index + 1] || null;
      index += 1;
    } else if (current === "--output") {
      args.output = argv[index + 1] || null;
      index += 1;
    }
  }
  if (!args.scenario) {
    throw new Error("Missing required --scenario argument.");
  }
  return args;
}

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function ensureCase(casePayload) {
  const caseId = casePayload && casePayload.id;
  if (!caseId) {
    throw new Error("Scenario must define case.id.");
  }
  const defaults = CASE_DEFAULTS[caseId] || {};
  return {
    id: caseId,
    name: casePayload.name || defaults.name || caseId,
    automation_level: casePayload.automation_level || defaults.automation_level || "semi_automatic",
  };
}

function inferDialogType(scenario, casePayload) {
  if (scenario.dialog && scenario.dialog.type) {
    return String(scenario.dialog.type);
  }
  const defaults = CASE_DEFAULTS[casePayload.id] || {};
  if (defaults.dialog_type) {
    return String(defaults.dialog_type);
  }
  throw new Error("Scenario must define dialog.type or use a known case.id.");
}

function resolveOutputPath(baseDir, caseId, cliOutput) {
  if (cliOutput) {
    return path.resolve(cliOutput);
  }
  return path.resolve(baseDir, "out", `${caseId}.result.json`);
}

function detectSandbox() {
  if (process.env.FLATPAK_ID) {
    return "flatpak";
  }
  if (process.env.SNAP) {
    return "snap";
  }
  if (process.env.APPIMAGE) {
    return "appimage";
  }
  return "none";
}

function buildPlatformPayload(scenario) {
  const incoming = scenario.platform || {};
  return {
    os: incoming.os || process.platform,
    distribution: incoming.distribution || process.env.XDG_CURRENT_DESKTOP || os.type(),
    version: incoming.version || os.release(),
    desktop_environment: incoming.desktop_environment || process.env.XDG_CURRENT_DESKTOP || "unknown",
    session_type: incoming.session_type || process.env.XDG_SESSION_TYPE || "unknown",
    sandbox: incoming.sandbox || detectSandbox(),
  };
}

function buildTargetPayload(scenario) {
  const incoming = scenario.target || {};
  if (incoming.name && incoming.version && incoming.sample_app) {
    return {
      name: String(incoming.name),
      version: String(incoming.version),
      sample_app: String(incoming.sample_app),
    };
  }
  return {
    name: TARGET_NAME,
    version: process.versions.electron || "unknown",
    sample_app: SAMPLE_APP_PATH,
  };
}

function normalizeFileTypes(fileTypes) {
  if (!Array.isArray(fileTypes) || fileTypes.length === 0) {
    return [];
  }
  return fileTypes.map((item) => {
    if (!Array.isArray(item) || item.length < 2) {
      throw new Error("dialog.filetypes entries must be [label, pattern] pairs.");
    }
    return {
      name: String(item[0]),
      extensions: String(item[1])
        .split(";")
        .map((value) => value.trim().replace(/^\*\./, "").replace(/^\./, ""))
        .filter(Boolean),
    };
  });
}

function executeSimulation(simulation, dialogType) {
  if (simulation.sleep_before_result_seconds != null) {
    const waitUntil = Date.now() + Number(simulation.sleep_before_result_seconds) * 1000;
    while (Date.now() < waitUntil) {
      // Busy-wait is acceptable here because it is only used in deterministic timeout simulation.
    }
  }

  if (simulation.cancel) {
    return { values: [], cancelled: true, returned_resource_type: "unknown", notes: [] };
  }
  if (dialogType === "probe_resource") {
    return executeProbeSimulation(simulation);
  }
  const selectedValues = dialogType === "open_files"
    ? (simulation.selected_paths || [])
    : (simulation.selected_path ? [simulation.selected_path] : []);
  const values = selectedValues.filter(Boolean).map((value) => String(value));
  const notes = [];
  if (simulation.selected_filter_label) {
    notes.push({
      code: "SELECTED_FILTER_LABEL",
      message: `Simulation recorded selected filter label '${String(simulation.selected_filter_label)}'.`,
    });
  }
  return { values, cancelled: values.length === 0, returned_resource_type: values.length ? "path" : "unknown", notes };
}

function executeProbeSimulation(simulation) {
  const probePath = simulation.probe_path ? String(simulation.probe_path) : "";
  if (!probePath) {
    return { values: [], cancelled: true, returned_resource_type: "unknown", notes: [] };
  }
  fs.mkdirSync(path.dirname(probePath), { recursive: true });
  if (simulation.revoke_access) {
    if (fs.existsSync(probePath)) {
      fs.unlinkSync(probePath);
    }
    return { values: [probePath], cancelled: false, returned_resource_type: "path", notes: [] };
  }
  if (simulation.persisted_access && !fs.existsSync(probePath)) {
    fs.writeFileSync(probePath, "FileGate persisted access fixture\n", "utf8");
  }
  return { values: [probePath], cancelled: false, returned_resource_type: "path", notes: [] };
}

function buildOpenDialogOptions(scenario, dialogType) {
  const dialogPayload = scenario.dialog || {};
  const properties = [];
  if (dialogType === "open_file") {
    properties.push("openFile");
  } else if (dialogType === "open_files") {
    properties.push("openFile", "multiSelections");
  } else if (dialogType === "open_folder") {
    properties.push("openDirectory");
  }
  if (dialogPayload.mustexist !== false) {
    properties.push("dontAddToRecent");
  }
  const options = {
    title: dialogPayload.title,
    defaultPath: dialogPayload.initialdir || dialogPayload.initialfile,
    properties,
  };
  const filters = normalizeFileTypes(dialogPayload.filetypes);
  if (filters.length > 0) {
    options.filters = filters;
  }
  return options;
}

function buildSaveDialogOptions(scenario) {
  const dialogPayload = scenario.dialog || {};
  const defaultName = dialogPayload.initialfile || "output.txt";
  const defaultPath = dialogPayload.initialdir
    ? path.join(dialogPayload.initialdir, defaultName)
    : defaultName;
  const options = {
    title: dialogPayload.title,
    defaultPath,
  };
  const filters = normalizeFileTypes(dialogPayload.filetypes);
  if (filters.length > 0) {
    options.filters = filters;
  }
  if (dialogPayload.defaultextension) {
    options.defaultPath = options.defaultPath.endsWith(dialogPayload.defaultextension)
      ? options.defaultPath
      : `${options.defaultPath}${dialogPayload.defaultextension}`;
  }
  return options;
}

async function executeSelection(mainWindow, scenario, dialogType) {
  const simulation = scenario.simulation || {};
  if (simulation.enabled) {
    const selection = executeSimulation(simulation, dialogType);
    selection.notes.push({
      code: "SIMULATED",
      message: "Result was produced using the documented simulation mode rather than an interactive Electron dialog.",
    });
    return selection;
  }

  if (dialogType === "probe_resource") {
    throw new Error("Interactive probe_resource mode is not implemented for the Electron sample target.");
  }

  if (dialogType === "save_file") {
    const response = await dialog.showSaveDialog(mainWindow, buildSaveDialogOptions(scenario));
    const filePath = response.filePath ? [response.filePath] : [];
    return {
      values: filePath,
      cancelled: Boolean(response.canceled),
      returned_resource_type: filePath.length ? "path" : "unknown",
      notes: [],
    };
  }

  const response = await dialog.showOpenDialog(mainWindow, buildOpenDialogOptions(scenario, dialogType));
  return {
    values: (response.filePaths || []).map((value) => String(value)),
    cancelled: Boolean(response.canceled),
    returned_resource_type: (response.filePaths || []).length ? "path" : "unknown",
    notes: [],
  };
}

function computeAccessFlags(dialogType, values) {
  if (!values.length) {
    return { can_read: false, can_write: false };
  }
  if (dialogType === "open_files") {
    return {
      can_read: values.every((value) => canAccess(value, fs.constants.R_OK)),
      can_write: false,
    };
  }
  const value = values[0];
  if (dialogType === "open_file" || dialogType === "open_folder" || dialogType === "probe_resource") {
    return {
      can_read: canAccess(value, fs.constants.R_OK),
      can_write: canAccess(value, fs.constants.W_OK),
    };
  }
  if (dialogType === "save_file") {
    if (fs.existsSync(value)) {
      return {
        can_read: canAccess(value, fs.constants.R_OK),
        can_write: canAccess(value, fs.constants.W_OK),
      };
    }
    return {
      can_read: false,
      can_write: canAccess(path.dirname(value), fs.constants.W_OK),
    };
  }
  return { can_read: false, can_write: false };
}

function canAccess(targetPath, mode) {
  try {
    fs.accessSync(targetPath, mode);
    return true;
  } catch {
    return false;
  }
}

function validateSelectionCount(scenario, casePayload, selection) {
  const expectation = scenario.expectation || {};
  let exactCount = expectation.expected_selection_count;
  let minCount = expectation.min_selection_count;
  let maxCount = expectation.max_selection_count;

  if (exactCount == null) {
    if (casePayload.id === "open_file_single") {
      exactCount = 1;
    } else if (casePayload.id === "open_file_multiple" && minCount == null) {
      minCount = 2;
    }
  }

  const issues = [];
  const actualCount = selection.values.length;
  if (exactCount != null && actualCount !== Number(exactCount)) {
    issues.push({
      code: "SELECTION_COUNT_MISMATCH",
      message: `Scenario expected exactly ${Number(exactCount)} selected path(s), but received ${actualCount}.`,
    });
  }
  if (minCount != null && actualCount < Number(minCount)) {
    issues.push({
      code: "SELECTION_COUNT_TOO_LOW",
      message: `Scenario expected at least ${Number(minCount)} selected path(s), but received ${actualCount}.`,
    });
  }
  if (maxCount != null && actualCount > Number(maxCount)) {
    issues.push({
      code: "SELECTION_COUNT_TOO_HIGH",
      message: `Scenario expected at most ${Number(maxCount)} selected path(s), but received ${actualCount}.`,
    });
  }
  return issues;
}

function normalizeExtensions(values) {
  if (!Array.isArray(values)) {
    return [];
  }
  return values
    .map((value) => String(value).trim().toLowerCase())
    .filter(Boolean);
}

function evaluateFilterExpectations(scenario, dialogType, selection) {
  const dialogPayload = scenario.dialog || {};
  const expectation = scenario.expectation || {};
  const notes = [];
  const fileTypes = normalizeFileTypes(dialogPayload.filetypes);

  if (fileTypes.length > 0) {
    const configured = fileTypes
      .map((item) => `${item.name} (${item.extensions.map((extension) => `*.${extension}`).join(";") || "*.*"})`)
      .join(", ");
    notes.push({
      code: "CONFIGURED_FILTERS",
      message: `Configured dialog filters: ${configured}.`,
    });
  }

  if (expectation.selected_filter_label) {
    notes.push({
      code: "FILTER_INTENT",
      message: `Scenario exercised filter intent '${String(expectation.selected_filter_label)}'.`,
    });
  }

  if (dialogType !== "open_file" || selection.cancelled || !selection.values.length) {
    return { notes, status: null };
  }

  const allowedExtensions = new Set(normalizeExtensions(expectation.allowed_extensions));
  if (allowedExtensions.size === 0) {
    return { notes, status: null };
  }

  const selectedExtension = path.extname(selection.values[0]).toLowerCase();
  if (allowedExtensions.has(selectedExtension)) {
    notes.push({
      code: "FILTER_MATCHED_SELECTION",
      message: `Selected file extension '${selectedExtension}' matched the allowed filter set ${JSON.stringify(Array.from(allowedExtensions).sort())}.`,
    });
    return { notes, status: null };
  }

  notes.push({
    code: "FILTER_MISMATCH",
    message: `Selected file extension '${selectedExtension || "(none)"}' did not match the allowed filter set ${JSON.stringify(Array.from(allowedExtensions).sort())}. Native dialogs may allow manual override or expose filters as advisory only.`,
  });
  return { notes, status: "warn" };
}

function evaluateSaveExpectations(scenario, dialogType, selection) {
  const expectation = scenario.expectation || {};
  const notes = [];
  if (dialogType !== "save_file" || selection.cancelled || !selection.values.length) {
    return { notes, status: null };
  }

  const selectedExtension = path.extname(selection.values[0]).toLowerCase();
  const expectedExtension = String(expectation.expected_extension || "").toLowerCase();

  if (expectation.expect_auto_append && expectedExtension) {
    if (selectedExtension === expectedExtension) {
      notes.push({
        code: "AUTO_APPEND_OBSERVED",
        message: `Returned save path used extension '${selectedExtension}', matching the configured default extension.`,
      });
      return { notes, status: null };
    }
    notes.push({
      code: "AUTO_APPEND_NOT_OBSERVED",
      message: `Returned save path used extension '${selectedExtension || "(none)"}' instead of the configured default extension '${expectedExtension}'. Some dialog backends treat default extensions as advisory only.`,
    });
    return { notes, status: "warn" };
  }

  const mismatchedExtension = String(expectation.mismatched_extension || "").toLowerCase();
  if (mismatchedExtension && expectedExtension) {
    if (selectedExtension === mismatchedExtension) {
      notes.push({
        code: "WRONG_EXTENSION_PRESERVED",
        message: `Returned save path preserved the mismatched extension '${mismatchedExtension}' instead of coercing to '${expectedExtension}'.`,
      });
      return { notes, status: "warn" };
    }
    if (selectedExtension === expectedExtension) {
      notes.push({
        code: "WRONG_EXTENSION_CORRECTED",
        message: `Returned save path used the configured extension '${expectedExtension}' rather than the mismatched extension '${mismatchedExtension}'.`,
      });
      return { notes, status: null };
    }
    notes.push({
      code: "WRONG_EXTENSION_ALTERNATE_RESULT",
      message: `Returned save path used extension '${selectedExtension || "(none)"}', which differs from both the configured '${expectedExtension}' and mismatched '${mismatchedExtension}' extensions.`,
    });
    return { notes, status: "warn" };
  }

  return { notes, status: null };
}

function evaluatePathNamingExpectations(scenario, casePayload, selection) {
  const extensions = scenario.extensions || {};
  const pathExt = extensions.path || {};
  const expectation = scenario.expectation || {};
  const notes = [];
  let overrideStatus = null;

  if (selection.cancelled || !selection.values.length) {
    return { notes, status: null };
  }

  const selectedValue = selection.values[0];
  const pathVariant = pathExt.path_variant;

  if (expectation.expect_absolute_path || pathExt.expect_absolute) {
    const isAbsolute = path.isAbsolute(selectedValue);
    if (isAbsolute) {
      notes.push({ code: "PATH_IS_ABSOLUTE", message: `Returned path is absolute: '${selectedValue}'.` });
    } else {
      notes.push({ code: "PATH_NOT_ABSOLUTE", message: `Returned path '${selectedValue}' is not absolute.` });
      overrideStatus = "warn";
    }
  }

  if (pathVariant === "spaces_in_path" || expectation.expect_spaces_preserved) {
    if (selectedValue.includes(" ")) {
      notes.push({ code: "SPACES_PRESERVED", message: `Path spaces preserved correctly in '${selectedValue}'.` });
    } else {
      notes.push({ code: "SPACES_NOT_OBSERVED", message: `Returned path '${selectedValue}' does not contain spaces.` });
      overrideStatus = "warn";
    }
  }

  if (pathVariant === "unicode_filename" || pathVariant === "polish_diacritics") {
    try {
      Buffer.from(selectedValue, "utf8").toString("utf8");
      notes.push({ code: "UNICODE_PRESERVED", message: `Unicode characters appear preserved in '${selectedValue}'.` });
    } catch (encErr) {
      notes.push({ code: "UNICODE_CORRUPTION", message: `Returned path contains invalid UTF-8 sequences: ${encErr}.` });
      overrideStatus = "fail";
    }
  }

  const minFilenameLength = expectation.min_filename_length;
  if (minFilenameLength != null || pathVariant === "very_long_filename") {
    const returnedBasename = path.basename(selectedValue);
    const actualLen = returnedBasename.length;
    const threshold = Number(minFilenameLength || 200);
    if (actualLen >= threshold) {
      notes.push({ code: "LONG_FILENAME_PRESERVED", message: `Filename length ${actualLen} meets minimum ${threshold}.` });
    } else {
      notes.push({ code: "LONG_FILENAME_TRUNCATED", message: `Filename length ${actualLen} is below expected minimum ${threshold}.` });
      overrideStatus = "warn";
    }
  }

  if (pathVariant === "nested_directory") {
    const parts = selectedValue.split(path.sep).filter(Boolean);
    const depth = parts.length - 1;
    const nestingDepth = pathExt.nesting_depth || 4;
    notes.push({ code: "NESTING_DEPTH_OBSERVED", message: `Returned path has ${depth} directory components; expected nesting depth: ${nestingDepth}.` });
  }

  if (pathVariant === "case_sensitive_collision") {
    const basename = path.basename(selectedValue);
    notes.push({ code: "CASE_COLLISION_SELECTION", message: `Selected filename under case-collision scenario: '${basename}'.` });
  }

  if (casePayload.id === "save_file_overwrite" && selection.values.length > 0) {
    if (fs.existsSync(selectedValue)) {
      notes.push({ code: "OVERWRITE_TARGET_EXISTS", message: `Save destination '${selectedValue}' already exists; overwrite behavior was exercised.` });
    } else {
      notes.push({ code: "OVERWRITE_TARGET_ABSENT", message: `Save destination '${selectedValue}' does not exist at reporting time.` });
    }
  }

  return { notes, status: overrideStatus };
}

function classifyErrorCode(error) {
  const message = String(error.message || error).toLowerCase();
  if (message.includes("display") || message.includes("window")) {
    return "RESOURCE_UNAVAILABLE";
  }
  return "UNKNOWN_ERROR";
}

function buildResultPayload(scenario, casePayload, dialogType, selection, durationMs, error) {
  const expectation = scenario.expectation || {};
  const caseDefaults = CASE_DEFAULTS[casePayload.id] || {};
  const cancelExpected = Boolean(expectation.cancel_is_expected || caseDefaults.cancel_expected);
  const notes = [...(selection ? selection.notes : [])];

  if (error) {
    notes.push({ code: "EXECUTION_ERROR", message: String(error.message || error) });
    return {
      status: "unsupported",
      duration_ms: durationMs,
      returned_resource_type: "unknown",
      returned_value_example: null,
      can_read: false,
      can_write: false,
      error_code: classifyErrorCode(error),
      notes,
    };
  }

  if (selection.cancelled) {
    notes.push({ code: "USER_CANCELLED", message: "The dialog was cancelled and no resource was returned." });
    return {
      status: cancelExpected ? "pass" : "fail",
      duration_ms: durationMs,
      returned_resource_type: selection.returned_resource_type,
      returned_value_example: null,
      can_read: false,
      can_write: false,
      error_code: "USER_CANCELLED",
      notes,
    };
  }

  const access = computeAccessFlags(dialogType, selection.values);
  if (dialogType === "probe_resource" && selection.values.length > 0) {
    if (scenario.expectation?.persistence_case) {
      notes.push({
        code: "PERSISTENCE_PROBE",
        message: "This result records direct post-restart probing of the previously selected resource.",
      });
      if (!access.can_read && !access.can_write) {
        return {
          status: "warn",
          duration_ms: durationMs,
          returned_resource_type: selection.returned_resource_type,
          returned_value_example: selection.values[0],
          can_read: access.can_read,
          can_write: access.can_write,
          error_code: "PERSISTENCE_DENIED",
          notes,
        };
      }
    }
    if (scenario.expectation?.revocation_case) {
      notes.push({
        code: "REVOCATION_PROBE",
        message: "This result records direct probing after access revocation or resource removal.",
      });
      if (!access.can_read && !access.can_write) {
        return {
          status: "manual_required",
          duration_ms: durationMs,
          returned_resource_type: selection.returned_resource_type,
          returned_value_example: selection.values[0],
          can_read: access.can_read,
          can_write: access.can_write,
          error_code: "ACCESS_REVOKED",
          notes,
        };
      }
    }
  }

  const selectionCountIssues = validateSelectionCount(scenario, casePayload, selection);
  notes.push(...selectionCountIssues);

  const filterEvaluation = evaluateFilterExpectations(scenario, dialogType, selection);
  notes.push(...filterEvaluation.notes);
  const saveEvaluation = evaluateSaveExpectations(scenario, dialogType, selection);
  notes.push(...saveEvaluation.notes);
  const pathEvaluation = evaluatePathNamingExpectations(scenario, casePayload, selection);
  notes.push(...pathEvaluation.notes);

  if (!scenario.simulation?.enabled) {
    notes.push({
      code: "NATIVE_DIALOG_BEHAVIOR",
      message: "Electron native dialog behavior may vary by platform or desktop environment; compare notes before treating differences as regressions.",
    });
  }

  if (!scenario.simulation?.enabled && (casePayload.id.startsWith("filter_") || ["extension_auto_append_on_save", "wrong_extension_selected"].includes(casePayload.id))) {
    notes.push({
      code: "NATIVE_DIALOG_LIMITATION",
      message: "Electron does not expose deterministic APIs for reading the actively chosen native filter or proving whether the backend auto-appended an extension; results should be interpreted as best-effort observations from the returned path.",
    });
  }

  if (cancelExpected) {
    notes.push({
      code: "UNEXPECTED_SELECTION",
      message: "A resource was selected even though the scenario expected a cancel action.",
    });
  }

  const baseStatus = cancelExpected || selectionCountIssues.length > 0
    ? "fail"
    : (filterEvaluation.status === "warn" || saveEvaluation.status === "warn" || pathEvaluation.status === "warn" ? "warn"
      : pathEvaluation.status === "fail" ? "fail" : "pass");
  const access = computeAccessFlags(dialogType, selection.values);
  return {
    status: baseStatus,
    duration_ms: durationMs,
    returned_resource_type: selection.returned_resource_type,
    returned_value_example: dialogType === "open_files" ? selection.values : selection.values[0],
    can_read: access.can_read,
    can_write: access.can_write,
    error_code: null,
    notes,
  };
}

function validateResultPayload(payload) {
  for (const field of ["schema_version", "run_id", "platform", "target", "case", "result"]) {
    if (!(field in payload)) {
      throw new Error(`Result payload missing top-level field '${field}'.`);
    }
  }
  for (const field of ["id", "automation_level"]) {
    if (!(field in payload.case)) {
      throw new Error(`Result payload missing case.${field}.`);
    }
  }
  for (const field of ["status", "duration_ms", "returned_resource_type"]) {
    if (!(field in payload.result)) {
      throw new Error(`Result payload missing result.${field}.`);
    }
  }
  if (!RESULT_STATUSES.has(payload.result.status)) {
    throw new Error(`Unsupported result.status '${payload.result.status}'.`);
  }
  if (!Number.isInteger(payload.result.duration_ms) || payload.result.duration_ms < 0) {
    throw new Error("result.duration_ms must be a non-negative integer.");
  }
}

function generateRunId() {
  const timestamp = new Date().toISOString().replace(/:/g, "-").replace(/\.\d+Z$/, "Z");
  const desktop = (process.env.XDG_CURRENT_DESKTOP || "unknown").toLowerCase().replace(/\s+/g, "-");
  return `${timestamp}-${process.platform}-${desktop}-${TARGET_NAME}`;
}

function createWindow() {
  const window = new BrowserWindow({
    width: 640,
    height: 480,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  window.loadFile(path.join(__dirname, "renderer.html")).catch(() => {
    window.loadURL("data:text/html,<html><body><p>FileGate Electron sample</p><script src='renderer.js'></script></body></html>");
  });
  return window;
}

async function main() {
  const args = parseArgs(process.argv.slice(1));
  const scenarioPath = path.resolve(args.scenario);
  const baseDir = __dirname;
  const scenario = loadJson(scenarioPath);
  const casePayload = ensureCase(scenario.case || {});
  const dialogType = inferDialogType(scenario, casePayload);
  const outputPath = resolveOutputPath(baseDir, casePayload.id, args.output);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });

  let mainWindow = null;
  const started = Date.now();
  let selection = { values: [], cancelled: true, returned_resource_type: "unknown", notes: [] };
  let executionError = null;

  try {
    await app.whenReady();
    mainWindow = createWindow();
    selection = await executeSelection(mainWindow, scenario, dialogType);
  } catch (error) {
    executionError = error;
  }

  const resultPayload = {
    schema_version: SCHEMA_VERSION,
    run_id: scenario.run_id || generateRunId(),
    platform: buildPlatformPayload(scenario),
    target: buildTargetPayload(scenario),
    case: casePayload,
    result: buildResultPayload(
      scenario,
      casePayload,
      dialogType,
      selection,
      Math.max(0, Date.now() - started),
      executionError,
    ),
  };

  validateResultPayload(resultPayload);
  fs.writeFileSync(outputPath, `${JSON.stringify(resultPayload, null, 2)}\n`, "utf8");
  process.stdout.write(`${outputPath}\n`);

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.destroy();
  }
  await app.quit();
  process.exit(resultPayload.result.status === "pass" || resultPayload.result.status === "warn" || resultPayload.result.status === "manual_required" ? 0 : 1);
}

main();