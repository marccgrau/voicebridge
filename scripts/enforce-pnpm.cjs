#!/usr/bin/env node

const userAgent = process.env.npm_config_user_agent ?? "";

if (userAgent.includes("pnpm/")) {
  process.exit(0);
}

console.error("This repository uses pnpm only.");
console.error("Run: pnpm install");
process.exit(1);
