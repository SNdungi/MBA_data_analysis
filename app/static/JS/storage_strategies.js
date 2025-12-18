/* --- app/static/js/storage_strategies.js --- */

class NativeFileStrategy {
    constructor(studyId) {
        this.studyId = studyId;
        this.handle = null;
    }

    static isSupported() {
        return 'showDirectoryPicker' in window;
    }

    async connect() {
        try {
            this.handle = await window.showDirectoryPicker();
            await idbKeyval.set(`dir_handle_${this.studyId}`, this.handle);
            return true;
        } catch (e) {
            console.error("Native Picker Cancelled", e);
            return false;
        }
    }

    async reconnect() {
        this.handle = await idbKeyval.get(`dir_handle_${this.studyId}`);
        return !!this.handle;
    }

    /**
     * FIX: Added 'requestIfMissing' flag.
     * - On Page Load: pass false (Check only).
     * - On Button Click: pass true (Trigger Popup).
     */
    async checkPermission(requestIfMissing = false) {
        if (!this.handle) return false;
        
        const options = { mode: 'readwrite' };
        
        // 1. Check existing permission (Does not require user gesture)
        if ((await this.handle.queryPermission(options)) === 'granted') {
            return true;
        }
        
        // 2. Request permission (REQUIRES user gesture)
        if (requestIfMissing) {
            try {
                if ((await this.handle.requestPermission(options)) === 'granted') {
                    return true;
                }
            } catch (e) {
                console.error("Permission request failed or blocked:", e);
                return false;
            }
        }
        
        return false;
    }

    async write(filename, content) {
        if (!this.handle) throw new Error("No folder connected");
        // Verify permission again before writing, requesting if necessary (usually triggered by save click)
        if (!(await this.checkPermission(true))) throw new Error("Permission denied");
        
        const fileHandle = await this.handle.getFileHandle(filename, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(content);
        await writable.close();
    }

    async getFilesAsFormData(filenames) {
        const formData = new FormData();
        let count = 0;
        for (const name of filenames) {
            try {
                const fh = await this.handle.getFileHandle(name);
                const file = await fh.getFile();
                formData.append(name, file);
                count++;
            } catch (e) { /* File missing is fine */ }
        }
        return { formData, count };
    }

    getUiLabels() {
        return {
            connectBtn: '<i class="bi bi-folder-plus"></i> Connect Local Folder',
            status: 'Local Folder Connected',
            type: 'native'
        };
    }
}

class FallbackDbStrategy {
    constructor(studyId) {
        this.studyId = studyId;
    }
    static isSupported() { return true; }
    async connect() {
        await idbKeyval.set(`db_active_${this.studyId}`, true);
        return true;
    }
    async reconnect() {
        const isActive = await idbKeyval.get(`db_active_${this.studyId}`);
        return !!isActive;
    }
    async checkPermission() { return true; } // DB always has permission
    async write(filename, content) {
        const blob = new Blob([content], { type: 'text/csv' });
        await idbKeyval.set(`file_${this.studyId}_${filename}`, blob);
    }
    async getFilesAsFormData(filenames) {
        const formData = new FormData();
        let count = 0;
        for (const name of filenames) {
            const blob = await idbKeyval.get(`file_${this.studyId}_${name}`);
            if (blob) {
                const file = new File([blob], name, { type: blob.type });
                formData.append(name, file);
                count++;
            }
        }
        return { formData, count };
    }
    getUiLabels() {
        return {
            connectBtn: '<i class="bi bi-hdd-fill"></i> Initialize Browser Storage',
            status: 'Browser Storage Active',
            type: 'fallback'
        };
    }
}