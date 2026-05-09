const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("filegate", {
  target: "electron",
});