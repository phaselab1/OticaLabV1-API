import { formatTitleCase } from './text.util';

describe('formatTitleCase', () => {
  it('should format simple names to title case', () => {
    expect(formatTitleCase('joao silva')).toBe('Joao Silva');
  });

  it('should keep common brazilian prepositions lowercase when in between words', () => {
    expect(formatTitleCase('maria da silva')).toBe('Maria da Silva');
    expect(formatTitleCase('pedro de souza e oliveira')).toBe(
      'Pedro de Souza e Oliveira',
    );
  });

  it('should capitalize preposition if it is the first word', () => {
    expect(formatTitleCase('da silva santos')).toBe('Da Silva Santos');
  });

  it('should return empty string on null or undefined or whitespace', () => {
    expect(formatTitleCase(null)).toBe('');
    expect(formatTitleCase(undefined)).toBe('');
    expect(formatTitleCase('   ')).toBe('');
  });
});

