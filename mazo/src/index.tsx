#!/usr/bin/env bun
import React from 'react';
import { render } from 'ink';
import { config } from 'dotenv';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { CLI } from './cli.js';

// Load environment variables from parent directory (where the shared .env is)
const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, '../../.env'), quiet: true });
// Also try loading from current directory as fallback
config({ quiet: true });

// Render the CLI app
render(<CLI />);
