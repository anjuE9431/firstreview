document.addEventListener('DOMContentLoaded', () => {
  // auto-dismiss flash messages
  setTimeout(() => {
    document.querySelectorAll('.flash li').forEach(li => li.remove());
  }, 4000);
});
