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

})

Alpine.start();



