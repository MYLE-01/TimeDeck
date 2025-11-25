function getDayShiftsFor(dateStr, code, shiftsData) {
  const targetDate = new Date(dateStr);
  const result = [];

  for (const shift of shiftsData.Shifts) {
    try {
      const startDate = new Date(shift.first);
      const daysSinceStart = Math.floor((targetDate - startDate) / (1000 * 60 * 60 * 24));
      if (daysSinceStart < 0) continue;

      const seq = shift.shift_sequence;
      const index = daysSinceStart % seq.length;
      const seqCode = seq[index];

      if (seqCode === code) {
        result.push({
          name: shift.name,
          type: code === "D" ? "Day" : "Night"
        });
      }
    } catch (err) {
      console.warn(`⚠️ Error parsing shift ${shift.name}:`, err);
    }
  }

  return result;
}
