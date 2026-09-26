/**
 * High-quality Text-to-Speech normalization and voice selector for YojanSetu.
 * Prepares natural spoken dialogue free from markdown noise, bullet punctuation, and raw URLs.
 */

export function cleanTextForSpeech(rawText: string, lang: 'hi' | 'en' = 'hi'): string {
  if (!rawText) return '';

  let text = rawText;

  // 1. Remove markdown bold, italic, code, headers
  text = text.replace(/[*_#`~>]/g, ' ');

  // 2. Replace currency symbol with natural spoken words
  if (lang === 'hi') {
    text = text.replace(/₹\s*(\d[\d,]*)/g, '$1 रुपये');
    text = text.replace(/₹/g, ' रुपये ');
  } else {
    text = text.replace(/₹\s*(\d[\d,]*)/g, '$1 rupees');
    text = text.replace(/₹/g, ' rupees ');
  }

  // 3. Strip URLs
  text = text.replace(/https?:\/\/\S+/g, '');

  // 4. Strip excessive bracketed tags like [RAJ-PEN-001]
  text = text.replace(/\[[^\]]*\]/g, '');

  // 5. Remove emojis and special pictograms
  text = text.replace(/([\uD800-\uDBFF][\uDC00-\uDFFF]|[\u2600-\u26FF]|[\u2700-\u27BF])/g, '');

  // 6. Condense numbered list items into natural flowing pauses
  text = text.replace(/^\s*\d+\.\s*/gm, ', ');
  text = text.replace(/^\s*[-•]\s*/gm, ', ');

  // 7. Normalize spaces and multiple newlines into pauses
  text = text.replace(/\n+/g, '। ');
  text = text.replace(/\s+/g, ' ').trim();

  // If the text is very long (e.g., includes all documents and kiosk details),
  // extract the core spoken summary (the first 2-3 sentences) so the audio doesn't ramble
  const sentences = lang === 'hi' ? text.split(/[।!?]+/) : text.split(/[.!?]+/);
  if (sentences.length > 4) {
    const summary = sentences.slice(0, 3).filter((s) => s.trim().length > 0).join(lang === 'hi' ? '। ' : '. ');
    if (lang === 'hi') {
      return `${summary}। अधिक जानकारी और दस्तावेज़ सूची नीचे स्क्रीन पर देखें।`;
    } else {
      return `${summary}. You can view the complete document list and details on screen below.`;
    }
  }

  return text;
}

/**
 * Finds the highest-fidelity available synthesis voice in the user's browser.
 */
export function findBestVoice(lang: 'hi' | 'en' = 'hi'): SpeechSynthesisVoice | null {
  if (typeof window === 'undefined' || !window.speechSynthesis) return null;

  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return null;

  if (lang === 'hi') {
    // 1. Check for premium/native Hindi voices
    const hindiVoice = voices.find(
      (v) =>
        (v.lang === 'hi-IN' || v.lang === 'hi_IN' || v.lang.startsWith('hi')) &&
        (v.name.includes('Google') || v.name.includes('Hemant') || v.name.includes('Kalpana') || v.name.includes('Natural'))
    );
    if (hindiVoice) return hindiVoice;

    // 2. Any Hindi voice
    const anyHindi = voices.find((v) => v.lang === 'hi-IN' || v.lang === 'hi_IN' || v.lang.startsWith('hi'));
    if (anyHindi) return anyHindi;
  }

  // Fallback to Indian English or regional English voice
  const indianEnglish = voices.find(
    (v) =>
      (v.lang === 'en-IN' || v.lang === 'en_IN') &&
      (v.name.includes('Google') || v.name.includes('Neerja') || v.name.includes('Prabhat'))
  );
  if (indianEnglish) return indianEnglish;

  // General English voice
  const anyEnglish = voices.find((v) => v.lang.startsWith('en'));
  return anyEnglish || voices[0] || null;
}
