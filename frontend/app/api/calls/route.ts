import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const CALLS_FILE = path.join(process.cwd(), 'public', 'calls.json');

function readCalls() {
  try {
    if (!fs.existsSync(CALLS_FILE)) {
      return [];
    }
    const data = fs.readFileSync(CALLS_FILE, 'utf-8');
    const parsed = JSON.parse(data);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.error('Error reading calls:', error);
    return [];
  }
}

function writeCalls(data: any) {
  try {
    const dir = path.dirname(CALLS_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(CALLS_FILE, JSON.stringify(data, null, 2), 'utf-8');
    return true;
  } catch (error) {
    console.error('Error writing calls:', error);
    return false;
  }
}

export async function GET() {
  const data = readCalls();
  return NextResponse.json(data);
}

export async function POST(request: Request) {
  try {
    const body = await request.json();

    // Check for developer reset action
    if (body.action === 'reset') {
      writeCalls([]);
      return NextResponse.json({ success: true, calls: [] });
    }

    const newCall = body;
    const calls = readCalls();

    if (!newCall.id) {
      return NextResponse.json({ success: false, error: 'Call ID is required' }, { status: 400 });
    }

    // Filter out existing call with same ID to avoid duplicates, then append
    const updatedCalls = calls.filter((c: any) => c.id !== newCall.id);
    updatedCalls.push(newCall);

    writeCalls(updatedCalls);

    return NextResponse.json({ success: true, call: newCall });
  } catch (error) {
    console.error('Error in calls API:', error);
    return NextResponse.json({ success: false, error: 'Invalid request' }, { status: 400 });
  }
}
