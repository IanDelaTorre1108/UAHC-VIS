document.getElementById("downloadBtn").addEventListener("click", function () {
    if (!currentCanvas) return;

    const { jsPDF } = window.jspdf;
    const qrImageData = currentCanvas.toDataURL("image/png");

    const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4'
    });

    const pageWidth = pdf.internal.pageSize.getWidth();
    const qrSize = 80;
    const x = (pageWidth - qrSize) / 2;
    const y = 70;

    const padding = 10;

    // Texts
    const header = "University of Antique";
    const footer = "Vehicle Information System";

    // Measure widths for header and footer text (to calculate box width)
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(14);
    const headerWidth = pdf.getTextWidth(header);

    pdf.setFontSize(12);
    const footerWidth = pdf.getTextWidth(footer);

    // Calculate box width as the max of QR size and text widths + padding * 2
    const boxWidth = Math.max(qrSize, headerWidth, footerWidth) + padding * 2;
    // Calculate box height to fit header text, QR code, footer text + vertical paddings
    const headerHeight = 14 * 0.35; // approx line height in mm for font size 14
    const footerHeight = 12 * 0.35; // approx line height for font size 12
    const boxHeight = headerHeight + qrSize + footerHeight + padding * 4;

    // Box top-left coordinates (centered horizontally, starts a bit above header)
    const boxX = (pageWidth - boxWidth) / 2;
    const boxY = y - headerHeight - padding * 2;

    // Draw border box
    pdf.setDrawColor(0); // black border
    pdf.rect(boxX, boxY, boxWidth, boxHeight);

    // Draw header text
    pdf.setTextColor(0, 0, 0);
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(14);
    pdf.text(header, pageWidth / 2, boxY + padding + headerHeight, { align: "center" });

    // Draw QR code centered below header text
    pdf.addImage(qrImageData, "PNG", (pageWidth - qrSize) / 2, boxY + padding * 2 + headerHeight, qrSize, qrSize);

    // Draw footer text below QR code
    pdf.setFontSize(12);
    pdf.text(footer, pageWidth / 2, boxY + padding * 3 + headerHeight + qrSize + footerHeight, { align: "center" });

    // Save PDF
    pdf.save("ua_vehicle_qr.pdf");
});
