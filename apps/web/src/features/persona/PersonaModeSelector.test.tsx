import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { PersonaModeSelector } from './PersonaModeSelector';
import { PersonaControlDrawer } from './PersonaControlDrawer';

describe('PersonaModeSelector', () => {
  it('renders Hina Prime as an available persona mode', () => {
    render(<PersonaModeSelector value="prime" onChange={() => {}} />);
    expect(screen.getByText(/Hina Prime/i)).toBeInTheDocument();
  });
});

describe('PersonaControlDrawer', () => {
  it('renders calibration sliders and principles when open', () => {
    render(<PersonaControlDrawer isOpen={true} onClose={() => {}} />);
    expect(screen.getByText(/HINA PERSONA PRIME/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Directness/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Sarcasm/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Technical Depth/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Formality/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/10 Sovereign Principles/i)).toBeInTheDocument();
  });
});
