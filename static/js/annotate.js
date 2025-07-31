document.addEventListener('DOMContentLoaded', function () {
    // Initialize Choices.js for multi-select user assignment
    const element = document.getElementById('responsible-users');
    const choices = new Choices(element, {
        removeItemButton: true,
        searchEnabled: true,
        maxItemCount: 10,
        placeholderValue: 'Type or select responsible users',
        searchPlaceholderValue: 'Type to search...',
        shouldSort: true
    });

    choices.input.focus();

    const nextBtn = document.getElementById('next-btn');

    // Read Flask-rendered data from data-attributes
    const body = document.body;
    const activeLineId = JSON.parse(body.getAttribute('data-active-line-id'));
    const receiptId = body.getAttribute('data-selected-receipt');

    // Collect line_ids from table rows dynamically (safer than template array)
    const lineIds = Array.from(document.querySelectorAll('tbody tr')).map(tr =>
        parseInt(tr.querySelector('td').textContent)
    );

    function goToNextLine() {
        if (!activeLineId || lineIds.length === 0) return;

        const selectedUsers = choices.getValue(true);

        nextBtn.disabled = true;
        nextBtn.textContent = "Saving...";

        fetch('/annotate/save-responsibility', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ line_id: activeLineId, user_names: selectedUsers })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                // move to next item as before
                const currentIndex = lineIds.indexOf(activeLineId);
                let nextIndex = currentIndex + 1;

                if (nextIndex >= lineIds.length) {
                    alert('Reached the last item!');
                    nextBtn.disabled = false;
                    nextBtn.textContent = "Next Item";
                    return;
                }

                const nextLineId = lineIds[nextIndex];
                const url = new URL(window.location.href);
                url.searchParams.set('active_line_id', nextLineId);
                if (receiptId) {
                    url.searchParams.set('receipt_id', receiptId);
                }
                window.location.href = url.toString();
            } else {
                alert('Failed to save responsibility mapping. Please try again.');
                nextBtn.disabled = false;
                nextBtn.textContent = "Next Item";
            }
        })
        .catch(err => {
            alert('Error saving responsibility mapping. Please try again.');
            console.error(err);
            nextBtn.disabled = false;
            nextBtn.textContent = "Next Item";
        });
    }



    nextBtn.addEventListener('click', goToNextLine);
});
