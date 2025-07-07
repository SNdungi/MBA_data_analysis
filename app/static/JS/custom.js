
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
