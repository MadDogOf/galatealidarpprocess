import fs from 'fs';
import * as THREE from 'three';
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js';

const buffer = fs.readFileSync('output/models/final/uploaded_scan_smplx_measurements.fbx');
console.log('FBX loaded from disk, length:', buffer.byteLength);

const loader = new FBXLoader();
try {
    const group = loader.parse(buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength), '');
    console.log('Parsed successfully! Children:', group.children.length);
} catch (e) {
    console.error('Error parsing:', e);
}
