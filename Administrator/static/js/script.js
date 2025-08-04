const sidebarToggle = document.getElementById('sidebarToggle');
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('overlay');

sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('show');
    overlay.style.display = sidebar.classList.contains('show') ? 'block' : 'none';
});

overlay.addEventListener('click', () => {
    sidebar.classList.remove('show');
    overlay.style.display = 'none';
});

document.getElementById('searchInput').addEventListener('input', function () {
    const filter = this.value.toLowerCase();
    const rows = document.querySelectorAll('table tbody tr');

    rows.forEach(row => {
        const ownerName = row.querySelector('td:nth-child(1)')?.textContent.toLowerCase() || "";
        const gatePass = row.querySelector('td:nth-child(2)')?.textContent.toLowerCase() || "";
        const address = row.querySelector('td:nth-child(4)')?.textContent.toLowerCase() || "";

        if (ownerName.includes(filter) || gatePass.includes(filter) || address.includes(filter)) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    });
});

function showQRModal(userId) {
    const owner = owners.find(o => o.user_id === userId);
    const qrData = `ID=${owner.user_id};VH-ID=${owner.vehicle_id}`;

    const qrContainer = document.getElementById("modal-qr-container");
    qrContainer.innerHTML = "";

    const qr = new QRCode(qrContainer, {
        text: qrData,
        width: 300,
        height: 300,
        correctLevel: QRCode.CorrectLevel.L
    });
    
    setTimeout(() => {
        const canvas = qrContainer.querySelector("canvas");
        if (!canvas) return;

        const ctx = canvas.getContext("2d");

        const img = new Image();
        img.src = "/static/images/ua1.png"; // Use a high-resolution logo

        img.onload = () => {
            const size = 50; // adjust size as needed
            const x = (canvas.width - size) / 2;
            const y = (canvas.height - size) / 2;

            // Optional: white background behind the logo
            ctx.fillStyle = "white";
            ctx.fillRect(x, y, size, size);

            // Enhance image rendering
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = "high";

            // Draw the logo
            ctx.drawImage(img, x, y, size, size);
            currentCanvas = canvas;
        };
    }, 300); // Wait a bit longer if QR takes time to render

    // Show Bootstrap modal
    const modal = new bootstrap.Modal(document.getElementById('qrModal'));
    modal.show();
}

function fetchOwnerData(userId) {
    fetch(`/get_owner/${userId}`)
    .then(response => response.json())
    .then(data => {
        document.getElementById('ownerProfilePic').src = `/uploads/profile/${data.profile_pic}`;
        document.querySelector('input[name="user_id"]').value = data.user_id;
        document.querySelector('input[name="last_name"]').value = data.last_name;
        document.querySelector('input[name="first_name"]').value = data.first_name;
        document.querySelector('input[name="middle_name"]').value = data.middle_name;
        document.querySelector('input[name="address"]').value = data.address;
        document.querySelector('input[name="phone"]').value = data.phone;
        document.querySelector('input[name="birthday"]').value = data.birthday;
        document.querySelector('input[name="place_of_birth"]').value = data.place_of_birth;
        document.querySelector('select[name="gender"]').value = data.gender;
        document.querySelector('select[name="civil_status"]').value = data.civil_status;

        document.querySelector('input[name="emergency_contact_name"]').value = data.emergency_name;
        document.querySelector('input[name="emergency_contact_number"]').value = data.emergency_phone;

        document.querySelector('input[name="license_no"]').value = data.license_number;
        document.querySelector('input[name="expiry"]').value = data.expiry;
        document.querySelector('input[name="vehicle_type"]').value = data.vehicle_type;
        document.querySelector('input[name="color"]').value = data.color;
        document.querySelector('input[name="brand"]').value = data.brand;
        document.querySelector('input[name="plate_number"]').value = data.plate_number;
        document.querySelector('input[name="franchise_no"]').value = data.franchise_no ?? '';
        document.querySelector('input[name="association"]').value = data.association;

        if (data.license_type) {
            document.querySelector(`input[name="license_type"][value="${data.license_type}"]`).checked = true;
        }
        if (data.ussage_classification) {
            document.querySelector(`input[name="ussage_classification"][value="${data.ussage_classification}"]`).checked = true;
            toggleForHireFields();
        }
    })
    .catch(err => {
        console.error("Failed to fetch owner data:", err);
        alert("Could not load owner data.");
    });
}

function enableInputs() {
    const form = document.querySelector('#editModal form');
    const inputs = form.querySelectorAll('input, select, textarea');
    
    inputs.forEach(input => {
        input.disabled = false;
    });
}

function deleteOwner(userId) {
    Swal.fire({
        title: 'Are you sure?',
        text: "This will permanently delete the owner and associated vehicle info.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Yes, delete it!'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/delete_owner/${userId}`, {
                method: 'DELETE'
            })
            .then(response => {
                if (response.ok) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Deleted!',
                        text: 'Owner record has been deleted.',
                        timer: 2000,
                        showConfirmButton: false
                    }).then(() => {
                        location.reload();
                    });
                } else {
                    Swal.fire('Error', 'Failed to delete owner.', 'error');
                }
            })
            .catch(error => {
                console.error("Error deleting owner:", error);
                Swal.fire('Error', 'An error occurred.', 'error');
            });
        }
    });
}





