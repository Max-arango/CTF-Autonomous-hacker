document.getElementById('hint-btn').addEventListener('click', function() {
    const hintDiv = document.getElementById('hint');
    hintDiv.classList.toggle('visible');
    hintDiv.classList.toggle('hidden');
    
    if (hintDiv.classList.contains('visible')) {
        hintDiv.innerHTML = 'Check the JavaScript console for another hint!';
        console.log('Hint: The flag might be in a variable or comment in this file');
        // flag{web_basic_flag_in_javascript_console_log}
    }
});

// Another flag reference
const secretFlag = "flag{web_basic_flag_in_javascript_variable}";
console.log("Debug: secretFlag variable exists");