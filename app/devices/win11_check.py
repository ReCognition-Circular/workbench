import re

def determine_win11_compatible(processor_str):
    """Determine Windows 11 compatibility from a processor description string.
    
    Rules:
        - Intel 8th gen (8000 series) or newer → YES
        - Intel 7th gen (7000 series) or older → NO
        - AMD Ryzen 2nd gen (2000 series) or newer → YES
        - Older AMD → NO
        - Unknown / unparseable → UNKNOWN
    """
    if not processor_str:
        return 'UNKNOWN'
    
    p = processor_str.lower().strip()
    
    # Check for 'Xth Gen' FIRST (e.g. "11th Gen Intel(R) Core(TM) i5-1135G7")
    match = re.search(r'(\d+)\s*(?:st|nd|rd|th)\s*gen', p)
    if match:
        gen = int(match.group(1))
        return 'YES' if gen >= 8 else 'NO'
    
    # Intel i3/i5/i7/i9-XXXX or i3/i5/i7/i9 XXXX
    match = re.search(r'i[3-9][-\s](\d{4})', p)
    if not match:
        match = re.search(r'i[3-9].*?(\d{4})', p)
    
    if match:
        model = match.group(1)
        if len(model) == 4:
            prefix = int(model[:2])
            if 10 <= prefix <= 19:
                gen = prefix  # 10th-19th gen
            else:
                gen = int(model[0])  # 1st-9th gen
        elif len(model) == 5:
            gen = int(model[:2])  # 10th gen+
        else:
            gen = 0
        
        return 'YES' if gen >= 8 else 'NO'
    
    # AMD Ryzen or Athlon
    if 'amd' in p or 'ryzen' in p or 'athlon' in p:
        match = re.search(r'(\d{4})', p)
        if match:
            gen = int(match.group(1)[0])
            return 'YES' if gen >= 2 else 'NO'
        return 'YES'  # Assume modern AMD if we have an AMD string
    
    # Intel with just 'I3', 'I5' etc and no model number - probably old
    if re.search(r'i[3-9]', p):
        return 'UNKNOWN'
    
    return 'UNKNOWN'
