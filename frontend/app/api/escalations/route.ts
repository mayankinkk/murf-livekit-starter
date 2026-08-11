import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const ESCALATIONS_FILE = path.join(process.cwd(), 'public', 'escalations.json');

function readEscalations() {
  try {
    if (!fs.existsSync(ESCALATIONS_FILE)) {
      return [];
    }
    const data = fs.readFileSync(ESCALATIONS_FILE, 'utf-8');
    const parsed = JSON.parse(data);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.error('Error reading escalations:', error);
    return [];
  }
}

function writeEscalations(data: any) {
  try {
    const dir = path.dirname(ESCALATIONS_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(ESCALATIONS_FILE, JSON.stringify(data, null, 2), 'utf-8');
    return true;
  } catch (error) {
    console.error('Error writing escalations:', error);
    return false;
  }
}

export async function GET() {
  const data = readEscalations();
  return NextResponse.json(data);
}

export async function POST(request: Request) {
  try {
    const newEscalation = await request.json();
    const escalations = readEscalations();

    // Check if we are updating status
    if (newEscalation.id && newEscalation.statusUpdateOnly) {
      const index = escalations.findIndex((e: any) => e.id === newEscalation.id);
      if (index !== -1) {
        escalations[index].status = newEscalation.status;
        writeEscalations(escalations);
        return NextResponse.json({ success: true, message: 'Status updated' });
      }
      return NextResponse.json({ success: false, message: 'Escalation not found' }, { status: 404 });
    }

    // Otherwise, append new escalation
    // If it doesn't have an ID, generate one (though the Python agent usually passes it)
    if (!newEscalation.id) {
      newEscalation.id = `ESC-${Math.floor(100000 + Math.random() * 900000)}`;
      newEscalation.created_at = new Date().toISOString();
      newEscalation.status = 'Open';
    }

    // Check if already exists (avoid duplicates)
    const exists = escalations.some((e: any) => e.id === newEscalation.id);
    if (!exists) {
      escalations.push(newEscalation);
      writeEscalations(escalations);
    }

    return NextResponse.json({ success: true, escalation: newEscalation });
  } catch (error) {
    console.error('Error in escalations API:', error);
    return NextResponse.json({ success: false, error: 'Invalid request' }, { status: 400 });
  }
}
