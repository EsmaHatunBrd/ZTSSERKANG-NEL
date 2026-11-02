import { setupServer } from "msw/node";
import { isleyiciler } from "./isleyiciler";

export const sunucu = setupServer(...isleyiciler);
