import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PublicPagination } from '@/components/PublicPagination';

const renderPagination = (
  currentPage: number,
  totalPages: number,
  buildHref = (p: number) => `/es/genres/techno?page=${p}`,
) =>
  render(
    <PublicPagination
      currentPage={currentPage}
      totalPages={totalPages}
      buildHref={buildHref}
      pageLabel={`Página ${currentPage} de ${totalPages}`}
      prevLabel="Anterior"
      nextLabel="Siguiente"
    />,
  );

describe('<PublicPagination />', () => {
  it('renders nothing when totalPages <= 1', () => {
    const { container } = renderPagination(1, 1);
    expect(container).toBeEmptyDOMElement();
  });

  it('on first page: prev is disabled span, next is link', () => {
    renderPagination(1, 5);
    const prev = screen.getByLabelText('Anterior');
    expect(prev.tagName).toBe('SPAN');
    expect(prev).toHaveAttribute('aria-disabled', 'true');

    const next = screen.getByRole('link', { name: 'Siguiente' });
    expect(next).toHaveAttribute('href', '/es/genres/techno?page=2');
  });

  it('on last page: prev is link, next is disabled span', () => {
    renderPagination(5, 5);
    const next = screen.getByLabelText('Siguiente');
    expect(next.tagName).toBe('SPAN');
    expect(next).toHaveAttribute('aria-disabled', 'true');

    const prev = screen.getByRole('link', { name: 'Anterior' });
    expect(prev).toHaveAttribute('href', '/es/genres/techno?page=4');
  });

  it('in the middle: both prev and next are active links', () => {
    renderPagination(3, 10);
    expect(screen.getByRole('link', { name: 'Anterior' })).toHaveAttribute(
      'href',
      '/es/genres/techno?page=2',
    );
    expect(screen.getByRole('link', { name: 'Siguiente' })).toHaveAttribute(
      'href',
      '/es/genres/techno?page=4',
    );
  });

  it('calls buildHref with the correct page numbers', () => {
    const buildHref = vi.fn((p: number) => `/x?p=${p}`);
    render(
      <PublicPagination
        currentPage={4}
        totalPages={9}
        buildHref={buildHref}
        pageLabel="x"
        prevLabel="Anterior"
        nextLabel="Siguiente"
      />,
    );
    expect(buildHref).toHaveBeenCalledWith(3);
    expect(buildHref).toHaveBeenCalledWith(5);
  });

  it('shows the page label', () => {
    renderPagination(3, 10);
    expect(screen.getByText('Página 3 de 10')).toBeInTheDocument();
  });
});
