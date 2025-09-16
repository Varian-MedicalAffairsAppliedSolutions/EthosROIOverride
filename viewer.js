// DICOM Viewer Module with Cornerstone3D
// Provides 4-up view with WebGL acceleration for smooth scrolling

import * as cornerstone3D from '@cornerstonejs/core';
import * as cornerstone3DTools from '@cornerstonejs/tools';
import { init as csRenderInit } from '@cornerstonejs/core';
import { init as csToolsInit } from '@cornerstonejs/tools';

const {
    RenderingEngine,
    Enums,
    volumeLoader,
    CONSTANTS,
    cache,
    metaData,
    utilities
} = cornerstone3D;

const {
    ViewportType,
    OrientationAxis
} = Enums;

class DicomViewer {
    constructor() {
        this.renderingEngineId = 'myRenderingEngine';
        this.viewportIds = {
            axial: 'CT_AXIAL',
            sagittal: 'CT_SAGITTAL',
            coronal: 'CT_CORONAL',
            volume3D: 'CT_3D'
        };
        
        this.volumeIds = {
            original: 'cornerstoneStreamingImageVolume:original',
            burned: 'cornerstoneStreamingImageVolume:burned'
        };
        
        this.renderingEngine = null;
        this.currentVolumeId = null;
        this.isShowingBurned = false;
        this.roiVisibility = {};
        this.windowPresets = {
            'Soft Tissue': { window: 400, level: 40 },
            'Lung': { window: 1500, level: -600 },
            'Bone': { window: 1500, level: 300 },
            'Brain': { window: 80, level: 40 }
        };
        
        this.currentWindow = { window: 400, level: 40 };
        this.originalData = null;
        this.burnedData = null;
        this.roiContours = {};
        this.initialized = false;
    }
    
    async initialize() {
        if (this.initialized) return;
        
        // Initialize Cornerstone3D
        await csRenderInit();
        await csToolsInit();
        
        // Create rendering engine
        this.renderingEngine = new RenderingEngine(this.renderingEngineId);
        
        // Add tools
        cornerstone3DTools.addTool(cornerstone3DTools.PanTool);
        cornerstone3DTools.addTool(cornerstone3DTools.ZoomTool);
        cornerstone3DTools.addTool(cornerstone3DTools.WindowLevelTool);
        cornerstone3DTools.addTool(cornerstone3DTools.StackScrollMouseWheelTool);
        cornerstone3DTools.addTool(cornerstone3DTools.CrosshairsTool);
        
        this.initialized = true;
    }
    
    async loadVolumes(originalCTData, burnedCTData, rtstructData) {
        this.originalData = originalCTData;
        this.burnedData = burnedCTData;
        
        // Convert CT data to Cornerstone format
        const originalVolume = await this.createVolumeFromCT(originalCTData, this.volumeIds.original);
        const burnedVolume = await this.createVolumeFromCT(burnedCTData, this.volumeIds.burned);
        
        // Parse ROI contours from RTSTRUCT
        if (rtstructData) {
            this.parseROIContours(rtstructData);
        }
        
        // Set current volume to original
        this.currentVolumeId = this.volumeIds.original;
        
        return { originalVolume, burnedVolume };
    }
    
    async createVolumeFromCT(ctData, volumeId) {
        // Sort CT slices by ImagePositionPatient[2]
        const sortedCT = ctData.sort((a, b) => {
            const zA = parseFloat(a.dataset.ImagePositionPatient[2]);
            const zB = parseFloat(b.dataset.ImagePositionPatient[2]);
            return zA - zB;
        });
        
        // Get metadata from first slice
        const firstSlice = sortedCT[0].dataset;
        const rows = firstSlice.Rows;
        const columns = firstSlice.Columns;
        const sliceThickness = parseFloat(firstSlice.SliceThickness || 1);
        const pixelSpacing = firstSlice.PixelSpacing;
        const imagePositionPatient = firstSlice.ImagePositionPatient;
        const imageOrientationPatient = firstSlice.ImageOrientationPatient;
        
        // Create volume
        const volume = await volumeLoader.createAndCacheVolume(volumeId, {
            dimensions: [columns, rows, sortedCT.length],
            spacing: [pixelSpacing[0], pixelSpacing[1], sliceThickness],
            origin: imagePositionPatient,
            direction: this.computeDirectionMatrix(imageOrientationPatient),
            metadata: {
                BitsAllocated: firstSlice.BitsAllocated,
                BitsStored: firstSlice.BitsStored,
                SamplesPerPixel: firstSlice.SamplesPerPixel || 1,
                HighBit: firstSlice.HighBit,
                PhotometricInterpretation: firstSlice.PhotometricInterpretation,
                PixelRepresentation: firstSlice.PixelRepresentation,
                WindowCenter: firstSlice.WindowCenter,
                WindowWidth: firstSlice.WindowWidth,
                RescaleIntercept: firstSlice.RescaleIntercept || 0,
                RescaleSlope: firstSlice.RescaleSlope || 1
            }
        });
        
        // Fill volume with pixel data
        const scalarData = volume.getScalarData();
        let offset = 0;
        
        for (const ctSlice of sortedCT) {
            const pixelData = new Int16Array(ctSlice.dicomData.dict['7FE00010'].Value[0]);
            const slope = parseFloat(ctSlice.dataset.RescaleSlope || 1);
            const intercept = parseFloat(ctSlice.dataset.RescaleIntercept || 0);
            
            // Apply rescale to get HU values
            for (let i = 0; i < pixelData.length; i++) {
                scalarData[offset + i] = pixelData[i] * slope + intercept;
            }
            offset += pixelData.length;
        }
        
        return volume;
    }
    
    computeDirectionMatrix(imageOrientationPatient) {
        // Convert DICOM image orientation to direction matrix
        const rowCosines = imageOrientationPatient.slice(0, 3);
        const columnCosines = imageOrientationPatient.slice(3, 6);
        
        // Compute normal vector (cross product)
        const normal = [
            rowCosines[1] * columnCosines[2] - rowCosines[2] * columnCosines[1],
            rowCosines[2] * columnCosines[0] - rowCosines[0] * columnCosines[2],
            rowCosines[0] * columnCosines[1] - rowCosines[1] * columnCosines[0]
        ];
        
        return [
            ...rowCosines,
            ...columnCosines,
            ...normal
        ];
    }
    
    parseROIContours(rtstructData) {
        const rtstruct = rtstructData.dataset;
        
        if (!rtstruct.ROIContourSequence) return;
        
        // Create ROI name to number mapping
        const roiMap = {};
        for (const roi of rtstruct.StructureSetROISequence) {
            roiMap[roi.ROINumber] = {
                name: roi.ROIName,
                color: this.getROIColor(roi.ROINumber, rtstruct)
            };
        }
        
        // Parse contours for each ROI
        for (const roiContour of rtstruct.ROIContourSequence) {
            const roiNumber = roiContour.ReferencedROINumber;
            const roiInfo = roiMap[roiNumber];
            
            if (!roiInfo || !roiContour.ContourSequence) continue;
            
            this.roiContours[roiInfo.name] = {
                color: roiInfo.color,
                contours: [],
                visible: true
            };
            
            for (const contour of roiContour.ContourSequence) {
                if (!contour.ContourData) continue;
                
                const points = [];
                for (let i = 0; i < contour.ContourData.length; i += 3) {
                    points.push([
                        parseFloat(contour.ContourData[i]),
                        parseFloat(contour.ContourData[i + 1]),
                        parseFloat(contour.ContourData[i + 2])
                    ]);
                }
                
                this.roiContours[roiInfo.name].contours.push({
                    points: points,
                    type: contour.ContourGeometricType
                });
            }
            
            this.roiVisibility[roiInfo.name] = true;
        }
    }
    
    getROIColor(roiNumber, rtstruct) {
        // Get color from RTSTRUCT or generate default
        if (rtstruct.ROIContourSequence) {
            for (const seq of rtstruct.ROIContourSequence) {
                if (seq.ReferencedROINumber === roiNumber && seq.ROIDisplayColor) {
                    const color = seq.ROIDisplayColor;
                    return `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
                }
            }
        }
        
        // Generate default color based on ROI number
        const colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', 
            '#FFEAA7', '#DDA0DD', '#98D8C8', '#FFD93D'
        ];
        return colors[roiNumber % colors.length];
    }
    
    async setupViewports() {
        const viewportElements = {
            axial: document.getElementById('viewport-axial'),
            sagittal: document.getElementById('viewport-sagittal'),
            coronal: document.getElementById('viewport-coronal'),
            volume3D: document.getElementById('viewport-3d')
        };
        
        const viewportInputArray = [
            {
                viewportId: this.viewportIds.axial,
                type: ViewportType.ORTHOGRAPHIC,
                element: viewportElements.axial,
                defaultOptions: {
                    orientation: OrientationAxis.AXIAL,
                    background: [0, 0, 0]
                }
            },
            {
                viewportId: this.viewportIds.sagittal,
                type: ViewportType.ORTHOGRAPHIC,
                element: viewportElements.sagittal,
                defaultOptions: {
                    orientation: OrientationAxis.SAGITTAL,
                    background: [0, 0, 0]
                }
            },
            {
                viewportId: this.viewportIds.coronal,
                type: ViewportType.ORTHOGRAPHIC,
                element: viewportElements.coronal,
                defaultOptions: {
                    orientation: OrientationAxis.CORONAL,
                    background: [0, 0, 0]
                }
            },
            {
                viewportId: this.viewportIds.volume3D,
                type: ViewportType.VOLUME_3D,
                element: viewportElements.volume3D,
                defaultOptions: {
                    background: [0, 0, 0]
                }
            }
        ];
        
        this.renderingEngine.setViewports(viewportInputArray);
        
        // Set volumes to viewports
        await this.setVolumesToViewports();
        
        // Setup tools
        this.setupTools();
        
        // Render
        this.renderingEngine.render();
    }
    
    async setVolumesToViewports() {
        const volume = cache.getVolume(this.currentVolumeId);
        
        for (const viewportId of Object.values(this.viewportIds)) {
            const viewport = this.renderingEngine.getViewport(viewportId);
            
            if (viewportId === this.viewportIds.volume3D) {
                // Setup 3D volume rendering
                await viewport.setVolumes([
                    {
                        volumeId: this.currentVolumeId,
                        callback: ({ volumeActor }) => {
                            volumeActor.getProperty().setInterpolationTypeToLinear();
                            volumeActor.getProperty().setShade(true);
                        }
                    }
                ]);
            } else {
                // Setup 2D orthographic views
                await viewport.setVolumes([{ volumeId: this.currentVolumeId }]);
            }
            
            // Apply window/level
            this.applyWindowLevel(viewport);
        }
    }
    
    setupTools() {
        const toolGroup = cornerstone3DTools.ToolGroupManager.createToolGroup('myToolGroup');
        
        // Add tools to group
        toolGroup.addTool(cornerstone3DTools.WindowLevelTool.toolName);
        toolGroup.addTool(cornerstone3DTools.PanTool.toolName);
        toolGroup.addTool(cornerstone3DTools.ZoomTool.toolName);
        toolGroup.addTool(cornerstone3DTools.StackScrollMouseWheelTool.toolName);
        toolGroup.addTool(cornerstone3DTools.CrosshairsTool.toolName);
        
        // Set active tools
        toolGroup.setToolActive(cornerstone3DTools.WindowLevelTool.toolName, {
            bindings: [{ mouseButton: cornerstone3DTools.Enums.MouseBindings.Primary }]
        });
        
        toolGroup.setToolActive(cornerstone3DTools.PanTool.toolName, {
            bindings: [{ mouseButton: cornerstone3DTools.Enums.MouseBindings.Auxiliary }]
        });
        
        toolGroup.setToolActive(cornerstone3DTools.ZoomTool.toolName, {
            bindings: [{ mouseButton: cornerstone3DTools.Enums.MouseBindings.Secondary }]
        });
        
        toolGroup.setToolActive(cornerstone3DTools.StackScrollMouseWheelTool.toolName);
        
        // Add viewports to tool group
        for (const viewportId of Object.values(this.viewportIds)) {
            toolGroup.addViewport(viewportId, this.renderingEngineId);
        }
    }
    
    applyWindowLevel(viewport) {
        const { window, level } = this.currentWindow;
        
        viewport.setProperties({
            voiRange: {
                lower: level - window / 2,
                upper: level + window / 2
            }
        });
    }
    
    setWindowPreset(presetName) {
        if (this.windowPresets[presetName]) {
            this.currentWindow = this.windowPresets[presetName];
            
            // Apply to all viewports
            for (const viewportId of Object.values(this.viewportIds)) {
                const viewport = this.renderingEngine.getViewport(viewportId);
                this.applyWindowLevel(viewport);
            }
            
            this.renderingEngine.render();
        }
    }
    
    toggleVolume() {
        this.isShowingBurned = !this.isShowingBurned;
        this.currentVolumeId = this.isShowingBurned ? 
            this.volumeIds.burned : this.volumeIds.original;
        
        // Update viewports with new volume
        this.setVolumesToViewports().then(() => {
            this.renderingEngine.render();
        });
        
        return this.isShowingBurned;
    }
    
    toggleROIVisibility(roiName) {
        if (this.roiContours[roiName]) {
            this.roiContours[roiName].visible = !this.roiContours[roiName].visible;
            this.roiVisibility[roiName] = this.roiContours[roiName].visible;
            this.renderROIOverlays();
        }
    }
    
    renderROIOverlays() {
        // This would render ROI contours as overlays on the viewports
        // Implementation depends on specific overlay rendering approach
        for (const [roiName, roiData] of Object.entries(this.roiContours)) {
            if (!roiData.visible) continue;
            
            // Render contours for this ROI
            this.drawROIContours(roiName, roiData);
        }
        
        this.renderingEngine.render();
    }
    
    drawROIContours(roiName, roiData) {
        // Draw ROI contours on viewports
        // This is a simplified version - actual implementation would
        // project 3D contours onto 2D viewport planes
        const { color, contours } = roiData;
        
        for (const contour of contours) {
            // Convert world coordinates to viewport coordinates
            // and draw using Canvas 2D or WebGL overlays
        }
    }
    
    navigateSlice(delta, viewportId) {
        const viewport = this.renderingEngine.getViewport(viewportId);
        const camera = viewport.getCamera();
        const { viewPlaneNormal, focalPoint } = camera;
        
        // Calculate new focal point
        const newFocalPoint = [
            focalPoint[0] + viewPlaneNormal[0] * delta,
            focalPoint[1] + viewPlaneNormal[1] * delta,
            focalPoint[2] + viewPlaneNormal[2] * delta
        ];
        
        camera.focalPoint = newFocalPoint;
        viewport.setCamera(camera);
        viewport.render();
    }
    
    resetView(viewportId) {
        const viewport = this.renderingEngine.getViewport(viewportId);
        viewport.resetCamera();
        viewport.render();
    }
    
    getSliceInfo(viewportId) {
        const viewport = this.renderingEngine.getViewport(viewportId);
        const camera = viewport.getCamera();
        const volume = cache.getVolume(this.currentVolumeId);
        
        if (!volume) return { current: 0, total: 0 };
        
        // Calculate current slice index based on camera position
        // This is simplified - actual calculation depends on orientation
        const dimensions = volume.dimensions;
        let totalSlices = 0;
        let currentSlice = 0;
        
        switch (viewportId) {
            case this.viewportIds.axial:
                totalSlices = dimensions[2];
                break;
            case this.viewportIds.sagittal:
                totalSlices = dimensions[0];
                break;
            case this.viewportIds.coronal:
                totalSlices = dimensions[1];
                break;
        }
        
        return { current: currentSlice, total: totalSlices };
    }
    
    exportCurrentView() {
        // Export current state for download
        return this.isShowingBurned ? this.burnedData : this.originalData;
    }
    
    destroy() {
        if (this.renderingEngine) {
            this.renderingEngine.destroy();
        }
        cache.purgeCache();
    }
}

// Export viewer instance
window.DicomViewer = DicomViewer;