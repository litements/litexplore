import Alpine from "/static/js/alpine.module.esm.js";
import persist from "/static/js/alpine.persist.module.esm.js";

window.Alpine = Alpine;
Alpine.plugin(persist);

Alpine.store("ltx", {
  // Using an array because a Set() doesn't play nicely with $persist
  common_sqlite_paths: Alpine.$persist(new Array()),
  common_sqlite_binaries: Alpine.$persist(new Array()),

  // Usage:
  // Alpine.store("ltx").add_sqlite_path(...)
  // Alpine.store("ltx").common_sqlite_paths

  add_sqlite_path(path) {
    if (this.common_sqlite_paths.includes(path)) {
      return;
    }
    this.common_sqlite_paths.push(path);
  },

  remove_sqlite_path(path) {
    const value_idx = array.indexOf(path);
    if (value_idx === -1) {
      return;
    }
    this.common_sqlite_paths.splice(value_idx, 1);
  },

  add_sqlite_bin(path) {
    if (this.common_sqlite_binaries.includes(path)) {
      return;
    }
    this.common_sqlite_binaries.push(path);
  },

  remove_sqlite_bin(path) {
    const value_idx = array.indexOf(path);
    if (value_idx === -1) {
      return;
    }
    this.common_sqlite_binaries.splice(value_idx, 1);
  },

  save() {
    let el;
    el = document.createElement("a");
    el.style = "display:none";
    let dataStr =
      "data:text/json;charset=utf-8," +
      encodeURIComponent(JSON.stringify(Alpine.raw(this)));
    el.href = dataStr;
    el.download = "litexplore-config.json";
    el.click();
    el.remove();
  },

  load() {
    let el;
    let loadedData;
    el = document.createElement("input");
    el.style = "display:none";
    el.id = "config_load";
    el.type = "file";
    el.accept = "application/JSON";
    try {
      el.addEventListener(
        "change",
        (evt) => {
          let reader = new FileReader();

          reader.onload = () => {
            loadedData = JSON.parse(reader.result);

            for (const [key, value] of Object.entries(loadedData)) {
              if (
                this.hasOwnProperty(key) &&
                typeof (this[key] != "function")
              ) {
                this[key] = value;
                console.log(`Loaded ${key} : ${value}`);
              }
            }
          };
          reader.readAsText(el.files[0]);
        },
        false
      );
      el.click();
    } catch {
      alert("Error loading config file");
    }
    el.remove();
  },
});

window.s = Alpine.store("ltx");

Alpine.start();
