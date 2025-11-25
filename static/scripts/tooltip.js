// Function to convert time input to HH:MM format
function convertToHHMM(input) {
    // Add your time conversion logic here (this is just an example)
    if (input.includes("h")) {
        let hours = parseFloat(input.replace('h', '').trim());
        let mins = Math.round((hours % 1) * 60);
        let formatted = `${Math.floor(hours)}:${mins < 10 ? "0" + mins : mins}`;
        return formatted;
    }
    // Handle other cases (e.g., 12:30, 12.3, etc.)
    return input;  // Modify as per your logic
}

// Function to attach tooltips to inputs
function attachTooltips() {
    // Get all input fields that contain a tooltip
    const inputFields = document.querySelectorAll('[id^="tooltip-"]');

    inputFields.forEach(inputField => {
        const fieldId = inputField.id.replace('tooltip-', ''); // Extract field id from tooltip id
        const inputElement = document.getElementById(fieldId); // Find the corresponding input element

        inputElement.addEventListener('input', function () {
            const inputValue = this.value;
            const tooltip = inputField;

            try {
                const convertedTime = convertToHHMM(inputValue);
                tooltip.textContent = convertedTime; // Update tooltip with converted time
                tooltip.style.visibility = 'visible';
                tooltip.style.opacity = '1';
                tooltip.style.transform = 'translateY(0)';
            } catch (e) {
                tooltip.style.visibility = 'hidden'; // Hide tooltip on error
                tooltip.style.opacity = '0';
                tooltip.style.transform = 'translateY(-10px)';
            }
        });
    });
}

// Call the function when the page loads
document.addEventListener('DOMContentLoaded', attachTooltips);
