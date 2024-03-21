import { FC } from "react";

interface ChatbotUISVGProps {
  theme: "dark" | "light"; // Note: This prop won't affect the new SVG but kept for interface consistency
  scale?: number;
}

export const ChatbotUISVG: FC<ChatbotUISVGProps> = ({ theme, scale = 1 }) => {
  return (
    <svg
      width={777 * scale}
      height={433 * scale}
      viewBox="0 0 777 433"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g transform="translate(0.000000,433.000000) scale(0.10000,-0.10000)" fill={`${theme === "dark" ? "#FFF" : "#000"}`} stroke="none">
        <path d="M2000 4323 c-627 -47 -1212 -363 -1582 -854 -180 -239 -319 -550 -377 -844 -62 -315 -49 -747 33 -1064 113 -438 353 -833 660 -1089 291 -242 647 -395 1051 -453 136 -19 449 -17 565 4 263 48 523 163 715 317 l50 39 3 -174 2 -175 485 0 485 0 0 1135 0 1135 -875 0 -875 0 0 -420 0 -420 368 0 367 -1 -79 -74 c-309 -292 -706 -405 -1081 -310 -153 39 -278 109 -399 224 -152 146 -253 342 -303 589 -25 124 -25 423 1 547 89 430 343 728 705 827 101 28 320 30 431 4 280 -65 519 -230 657 -455 l50 -80 431 330 c238 182 432 337 432 344 0 30 -150 235 -243 332 -282 292 -654 484 -1080 558 -180 30 -416 42 -597 28z"
        fill={`${theme === "dark" ? "#FFF" : "#000"}`}/>
        <path d="M4670 2165 l0 -2135 1550 0 1550 0 0 510 0 510 -965 0 -965 0 0 1625 0 1625 -585 0 -585 0 0 -2135z"
        fill={`${theme === "dark" ? "#FFF" : "#000"}`}/>
      </g>
    </svg>
  );
};
