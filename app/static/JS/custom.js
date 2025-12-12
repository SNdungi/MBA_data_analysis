


const SyncManager = {
    studyId: null,
    dirHandle: null,
    autoSaveInterval: null,
    isDirty: false, // Tracks if server has changes not yet saved to disk

    // Initialize: Connect, Check Permission, Upload to Server
    async init(studyId) {
        this.studyId = studyId;
        
        // 1. Get Handle from DB (using idb-keyval from previous step)
        this.dirHandle = await LocalFileManager.getDirectoryHandle(studyId);
        
        if (!this.dirHandle) {
            alert("Please connect your local folder.");
            return false;
        }

        // 2. Verify R/W Permission
        const hasPerm = await LocalFileManager.verifyPermission(this.dirHandle, true);
        if (!hasPerm) return false;

        // 3. Upload Local Files to Server Cache (Hydrate Session)
        await this.uploadLocalFilesToServer(['original.csv', 'mapper.json', 'codebook.json']);
        
        // 4. Start Auto-Save (Every 60 seconds)
        this.startAutoSave();
        
        // 5. Cleanup on tab close
        window.addEventListener('beforeunload', () => {
            // Optional: Fire a beacon to clean server
            navigator.sendBeacon(`/projects/workspace/close/${this.studyId}`);
        });

        return true;
    },

    async uploadLocalFilesToServer(filenames) {
        const formData = new FormData();
        
        for (const name of filenames) {
            try {
                const fileHandle = await this.dirHandle.getFileHandle(name);
                const file = await fileHandle.getFile();
                formData.append(name, file);
            } catch (e) {
                console.log(`Skipping ${name}, not found locally.`);
            }
        }

        await fetch(`/projects/workspace/sync_up/${this.studyId}`, {
            method: 'POST',
            body: formData
        });
        console.log("☁️ Workspace hydrated on server.");
    },

    // Call this after any AJAX operation that modifies data (e.g., Run Bootstrap, Encode)
    async pullFromServerAndSave(filename) {
        console.log(`⬇️ Syncing ${filename} from server...`);
        
        const response = await fetch(`/projects/workspace/sync_down/${this.studyId}/${filename}`);
        if (!response.ok) return;

        const data = await response.json();
        
        // Write to local disk using File System Access API
        await LocalFileManager.writeFile(this.dirHandle, filename, data.content);
        
        // Update UI
        this.showSavedToast();
    },

    startAutoSave() {
        // Example: Poll server for 'simulated_data.csv' or just save specific files periodically
        // For a simple app, it's better to trigger saves explicitly after actions.
        // But here is a timed backup of the mapper:
        this.autoSaveInterval = setInterval(() => {
            this.pullFromServerAndSave('mapper.json');
        }, 60000); // 60 seconds
    },

    showSavedToast() {
        // Simple visual feedback
        const el = document.getElementById('saveStatus');
        if(el) {
            el.innerHTML = '<i class="fas fa-check-circle text-success"></i> Saved to Disk';
            setTimeout(() => el.innerHTML = '', 3000);
        }
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
