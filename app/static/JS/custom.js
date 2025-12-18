/* --- custom.js --- */

const LocalFileManager = {
    async getDirectoryHandle(studyId) {
        return await idbKeyval.get(`dir_handle_${studyId}`);
    },

    async pickFolder(studyId) {
        if (!('showDirectoryPicker' in window)) {
            alert("Browser not supported. Use Chrome, Edge, or Opera.");
            return null;
        }
        try {
            const handle = await window.showDirectoryPicker();
            // This OVERWRITES the old handle, solving your "Reset" requirement
            await idbKeyval.set(`dir_handle_${studyId}`, handle);
            return handle;
        } catch (e) {
            console.error("Picker cancelled", e);
            return null;
        }
    },

    async verifyPermission(fileHandle, readWrite) {
        const options = {};
        if (readWrite) options.mode = 'readwrite';
        // Check if permission already exists
        if ((await fileHandle.queryPermission(options)) === 'granted') return true;
        // If not, we CANNOT request it automatically on load. User must click.
        return false;
    }
};

/* --- app/static/js/custom.js --- */

const SyncManager = {
    studyId: null,
    baseFilename: null,
    strategy: null,

    async init(studyId, baseFilename) {
        this.studyId = studyId;
        this.baseFilename = baseFilename;

        // 1. Factory
        if (NativeFileStrategy.isSupported()) {
            this.strategy = new NativeFileStrategy(studyId);
        } else {
            this.strategy = new FallbackDbStrategy(studyId);
        }

        // 2. Reconnect
        if (!(await this.strategy.reconnect())) {
            this.updateStatus('disconnected');
            this.toggleSetupAlert(true);
            return false;
        }

        // 3. Permission Check (PASSIVE ONLY)
        // Pass 'false' so we do NOT try to pop up the prompt on page load
        const hasPerm = await this.strategy.checkPermission(false);
        
        if (!hasPerm) {
            // Permission is missing. We must stop here.
            // We update the UI to ask the user to click.
            this.updateStatus('permission_needed');
            this.toggleSetupAlert(true);
            return false;
        }

        // 4. Online
        this.updateStatus('online');
        this.toggleSetupAlert(false);

        // 5. Auto-Hydrate
        const mapFile = this.baseFilename.replace('.csv', '.json');
        const simFile = `simulated_${this.baseFilename}`;
        await this.hydrateServer([this.baseFilename, mapFile, simFile]);

        return true;
    },

    // --- NEW: Explicit Authorization Action ---
    async authorizeStorage() {
        // This is called by the User Click, so 'requestIfMissing' = true is allowed here
        const hasPerm = await this.strategy.checkPermission(true);
        
        if (hasPerm) {
            // If granted, re-run init to finish hydration
            await this.init(this.studyId, this.baseFilename);
            window.location.reload();
        } else {
            alert("Permission was not granted. Please try again.");
        }
    },

    async syncProjectState() {
        if (!this.studyId || !this.baseFilename) return;
        this.showSavingIndicator(true);
        const filesToSync = [
            this.baseFilename,
            this.baseFilename.replace('.csv', '.json'),
            `simulated_${this.baseFilename}`,
            `${this.baseFilename.replace('.csv', '')}_encoded.csv`, // Add encoded files
            `${this.baseFilename.replace('.csv', '')}_codebook.json`
        ];
        let successCount = 0;
        for (const filename of filesToSync) {
            const result = await this.pullFromServerAndSave(filename, true);
            if (result) successCount++;
        }
        this.showSavingIndicator(false);
        if (successCount > 0) this.showSavedToast(`Synced ${successCount} files`);
    },

    async pullFromServerAndSave(filename, silent = false) {
        // Here we can request permission because this function is triggered by a Save Click
        if (!(await this.strategy.reconnect())) {
            if(!silent) alert("Storage not connected.");
            return false;
        }
        
        if(!silent) this.showSavingIndicator(true);

        try {
            // Verify/Request permission before write
            if (!(await this.strategy.checkPermission(true))) {
                throw new Error("Permission denied");
            }

            const res = await fetch(`/projects/workspace/sync_down/${this.studyId}/${filename}`);
            if (res.status === 404) return false;
            
            if (!res.ok) throw new Error("Server Error");
            const data = await res.json();
            
            await this.strategy.write(filename, data.content);
            
            if(!silent) this.showSavedToast();
            return true;

        } catch (e) {
            console.error(`Failed to sync ${filename}`, e);
            if(!silent) alert(`Failed to save ${filename}: ${e.message}`);
            return false;
        } finally {
            if(!silent) this.showSavingIndicator(false);
        }
    },

    async hydrateServer(filenames) {
        const { formData, count } = await this.strategy.getFilesAsFormData(filenames);
        if (count > 0) {
            await fetch(`/projects/workspace/sync_up/${this.studyId}`, {
                method: 'POST', body: formData
            });
            if (document.body.innerText.includes("Waiting for Local Sync")) {
                window.location.reload();
            }
        }
    },
    
    async connectStorage() {
        const success = await this.strategy.connect();
        if (success) {
            await this.init(this.studyId, this.baseFilename);
            window.location.reload();
        }
    },
    
    updateStatus(status) {
        const el = document.getElementById('connectionStatus');
        const labels = this.strategy.getUiLabels();
        if (!el) return;
        
        // Clone to wipe old listeners
        const newEl = el.cloneNode(true);
        el.parentNode.replaceChild(newEl, el);
        const updatedEl = document.getElementById('connectionStatus');

        if (status === 'online') {
            updatedEl.className = "badge bg-success-subtle text-success me-3";
            updatedEl.innerHTML = `<i class="bi bi-check-circle"></i> ${labels.status}`;
            updatedEl.title = "Storage Active";
        } 
        else if (status === 'disconnected') {
            updatedEl.className = "badge bg-danger text-white me-3 animate-pulse";
            updatedEl.innerHTML = labels.connectBtn;
            updatedEl.style.cursor = 'pointer';
            updatedEl.onclick = () => this.connectStorage();
        } 
        else if (status === 'permission_needed') {
            updatedEl.className = "badge bg-warning text-dark me-3";
            updatedEl.innerHTML = '<i class="bi bi-shield-lock"></i> Authorize';
            updatedEl.style.cursor = 'pointer';
            // FIX: This click now calls authorizeStorage(), which triggers the prompt
            updatedEl.onclick = () => this.authorizeStorage();
        }
    },

    toggleSetupAlert(show) {
        const alertBox = document.getElementById('local-setup-alert');
        if (alertBox) {
            alertBox.style.display = show ? 'block' : 'none';
            // Update the button inside the alert too
            const btn = alertBox.querySelector('button');
            if(btn) {
                // If permission is needed, change button to Authorize
                if (show && this.strategy && this.strategy.handle) {
                     btn.innerHTML = '<i class="bi bi-shield-lock"></i> Click to Authorize Access';
                     btn.onclick = () => this.authorizeStorage();
                } else {
                     btn.onclick = () => this.connectStorage();
                }
            }
        }
    },

    showSavedToast(msg = 'Saved') {
        const el = document.getElementById('saveStatus');
        if(el) {
            el.innerHTML = `<span class="text-success"><i class="fas fa-check"></i> ${msg}</span>`;
            setTimeout(() => el.innerHTML = '', 3000);
        }
    },

    showSavingIndicator(isSaving) {
        const el = document.getElementById('saveStatus');
        if(el) el.innerHTML = isSaving ? '<i class="fas fa-spinner fa-spin text-muted"></i>' : '';
    }
};


  (function ($) {
  
  "use strict";

    // MENU
    $('#sidebarMenu .nav-link').on('click',function(){
      $("#sidebarMenu").collapse('hide');
    });
    
    // CUSTOM LINK
    $('.smoothscroll').click(function(){
      var el = $(this).attr('href');
      var elWrapped = $(el);
      var header_height = $('.navbar').height();
  
      scrollToDiv(elWrapped,header_height);
      return false;
  
      function scrollToDiv(element,navheight){
        var offset = element.offset();
        var offsetTop = offset.top;
        var totalScroll = offsetTop-navheight;
  
        $('body,html').animate({
        scrollTop: totalScroll
        }, 300);
      }
    });
  
  })(window.jQuery);

  
  // Apply validation to all number inputs
  const inputs = document.querySelectorAll('input[type="number"]');

  inputs.forEach(input => {
      input.setAttribute('min', '0');
      input.setAttribute('step', '0.05');

      input.addEventListener('input', function (e) {
          const value = parseFloat(e.target.value);
          if (value < 0) {
              e.target.value = 0; // Reset to 0 if less than minimum
              alert("Value cannot be less than 0.");
          } else if ((value * 100) % 5 !== 0) {
              alert("Value must be in increments of 0.05.");
          }
      });
  });
