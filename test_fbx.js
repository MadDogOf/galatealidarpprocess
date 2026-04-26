import fs from 'fs';
import * as THREE from 'three';
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js';

const fbxData = fs.readFileSync('output/models/final/uploaded_scan_smplx_measurements.fbx', 'utf8');
console.log('FBX loaded from disk, length:', fbxData.length);

const loader = new FBXLoader();
try {
    const group = loader.parse(fbxData, '');
    console.log('Parsed successfully! Children:', group.children.length);
} catch (e) {
    console.error('Error parsing:', e);
}
