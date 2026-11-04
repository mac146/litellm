import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AriaAvatar } from "./AriaAvatar";

describe("AriaAvatar", () => {
  it("renders a decorative icon sized by the size prop", () => {
    const { container } = render(<AriaAvatar size={40} />);

    const icon = container.firstElementChild as HTMLElement;
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(icon.style.width).toBe("40px");
    expect(icon.querySelector("svg")).not.toBeNull();
  });
});
