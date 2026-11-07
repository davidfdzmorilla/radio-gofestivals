import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FestivalCards } from "@/components/festivals/FestivalCards";
import type { Festival } from "@/lib/festivals";

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={`/en${href}`} {...rest}>
      {children}
    </a>
  ),
}));

// next/image necesita el optimizador; un <img> basta y deja disparar onError.
vi.mock("next/image", () => ({
  default: ({
    src,
    alt,
    onError,
  }: {
    src: string;
    alt: string;
    onError?: () => void;
  }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} onError={onError} />
  ),
}));

const IMG =
  "https://proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com/festivals/x/y.webp";

function festival(over: Partial<Festival> = {}): Festival {
  return {
    id: "17",
    name: "Rave on Snow Festival",
    startDate: "2026-12-10T00:00:00.000Z",
    endDate: "2026-12-13T00:00:00.000Z",
    location: "Saalbach, Austria",
    locationEn: null,
    countryCode: "AT",
    website: null,
    imageUrl: IMG,
    description: null,
    descriptionEn: null,
    genres: [],
    ...over,
  };
}

describe("FestivalCards images", () => {
  it("shows the festival image, hidden from assistive tech (the link already has the name)", () => {
    const { container } = render(
      <FestivalCards festivals={[festival()]} locale="en" />,
    );
    const img = container.querySelector("img");
    expect(img?.getAttribute("src")).toBe(IMG);
    expect(img?.getAttribute("alt")).toBe("");
    expect(screen.getByRole("link").textContent).toContain(
      "Rave on Snow Festival",
    );
  });

  it("does not load images from hosts outside the allow-list", () => {
    const { container } = render(
      <FestivalCards
        festivals={[
          festival({ imageUrl: "https://evil.example/festivals/a.webp" }),
        ]}
        locale="en"
      />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("RO");
  });

  it("falls back to initials on the given color when there is no image", () => {
    const { container } = render(
      <FestivalCards
        festivals={[festival({ imageUrl: null })]}
        locale="en"
        color="#ff0066"
      />,
    );
    expect(container.querySelector("img")).toBeNull();
    const box = container.querySelector(
      '[style*="background-color"]',
    ) as HTMLElement;
    expect(box.style.backgroundColor).toBe("rgb(255, 0, 102)");
  });

  it("falls back when the image fails to load", () => {
    const { container } = render(
      <FestivalCards festivals={[festival()]} locale="en" />,
    );
    fireEvent.error(container.querySelector("img") as HTMLImageElement);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("RO");
  });
});
