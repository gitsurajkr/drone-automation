#!/usr/bin/env python3
"""
Mission Planner Utility
========================
A utility to plan and validate waypoint missions before execution.
"""

import json
import math
from typing import List, Tuple, Dict, Any

class MissionPlanner:
    """Utility for planning and validating waypoint missions."""
    
    def __init__(self):
        self.waypoints = []
        self.mission_stats = {}
    
    def add_waypoint(self, lat: float, lon: float, alt: float = 20.0) -> bool:
        """Add a waypoint to the mission."""
        # Validate coordinates
        if not (-90 <= lat <= 90):
            print(f"❌ Invalid latitude: {lat} (must be -90 to 90)")
            return False
        
        if not (-180 <= lon <= 180):
            print(f"❌ Invalid longitude: {lon} (must be -180 to 180)")
            return False
        
        if not (0.5 <= alt <= 100):
            print(f"❌ Invalid altitude: {alt} (must be 0.5 to 100 meters)")
            return False
        
        self.waypoints.append((lat, lon, alt))
        print(f"✅ Added waypoint {len(self.waypoints)}: {lat:.6f}, {lon:.6f}, {alt}m")
        return True
    
    def remove_waypoint(self, index: int) -> bool:
        """Remove a waypoint by index."""
        if 0 <= index < len(self.waypoints):
            removed = self.waypoints.pop(index)
            print(f"Removed waypoint {index + 1}: {removed[0]:.6f}, {removed[1]:.6f}, {removed[2]}m")
            return True
        else:
            print(f"❌ Invalid waypoint index: {index + 1}")
            return False
    
    def calculate_distance(self, wp1: Tuple[float, float, float], wp2: Tuple[float, float, float]) -> float:
        """Calculate distance between two waypoints using NavigationUtils."""
        from .navigation_utils import NavigationUtils
        return NavigationUtils.calculate_distance(wp1[:2], wp2[:2])
    
    def calculate_mission_stats(self) -> Dict[str, Any]:
        """Calculate mission statistics using MissionCalculator."""
        from .navigation_utils import MissionCalculator
        
        stats = MissionCalculator.calculate_mission_stats(self.waypoints)
        self.mission_stats = stats
        return stats
    
    def validate_mission(self) -> Tuple[bool, List[str]]:
        """Validate the mission for safety and feasibility."""
        issues = []
        
        if len(self.waypoints) == 0:
            issues.append("No waypoints defined")
        
        # Check minimum waypoints
        if len(self.waypoints) < 2:
            issues.append("Need at least 2 waypoints for a mission")
        
        # Check for waypoints too close together
        if len(self.waypoints) > 1:
            for i in range(len(self.waypoints) - 1):
                distance = self.calculate_distance(self.waypoints[i], self.waypoints[i + 1])
                if distance < 2.0:
                    issues.append(f"Waypoints {i+1} and {i+2} are too close ({distance:.1f}m)")
        
        # Check mission distance
        stats = self.calculate_mission_stats()
        if stats["total_distance"] > 1000:  # 1km limit
            issues.append(f"Mission too long ({stats['total_distance']:.0f}m > 1000m)")
        
        # Check flight time
        if stats["estimated_flight_time"] > 600:  # 10 minute limit
            issues.append(f"Flight time too long ({stats['estimated_flight_time']:.0f}s > 600s)")
        
        # Check altitude consistency
        if stats["altitude_range"][1] - stats["altitude_range"][0] > 30:
            issues.append("Large altitude variations (>30m) detected")
        
        return len(issues) == 0, issues
    
    def print_mission_summary(self):
        """Print a detailed mission summary."""
        if not self.waypoints:
            print("❌ No waypoints defined")
            return
        
        stats = self.calculate_mission_stats()
        
        print("\n🗺️ Mission Summary")
        print("=" * 40)
        print(f"📍 Waypoints: {stats['total_waypoints']}")
        print(f"📏 Total distance: {stats['total_distance']:.0f}m")
        print(f"⏱️ Estimated flight time: {stats['estimated_flight_time']:.0f}s ({stats['estimated_flight_time']/60:.1f} min)")
        print(f"📈 Altitude range: {stats['altitude_range'][0]:.1f}m - {stats['altitude_range'][1]:.1f}m")
        
        if stats['bounding_box']:
            bb = stats['bounding_box']
            print(f"🗺️ Area: {bb['min_lat']:.6f} to {bb['max_lat']:.6f} (lat)")
            print(f"       {bb['min_lon']:.6f} to {bb['max_lon']:.6f} (lon)")
        
        print("\n📍 Waypoint Details:")
        for i, (lat, lon, alt) in enumerate(self.waypoints, 1):
            print(f"   {i}: {lat:.6f}, {lon:.6f}, {alt}m")
            
            if i > 1:
                distance = self.calculate_distance(self.waypoints[i-2], self.waypoints[i-1])
                print(f"      Distance from previous: {distance:.0f}m")
        
        # Validation
        is_valid, issues = self.validate_mission()
        if is_valid:
            print("\n✅ Mission validation passed")
        else:
            print("\n⚠️ Mission validation issues:")
            for issue in issues:
                print(f"   - {issue}")
    
    def save_mission(self, filename: str) -> bool:
        """Save mission to JSON file."""
        try:
            mission_data = {
                "waypoints": self.waypoints,
                "stats": self.calculate_mission_stats(),
                "created": "2025-10-04T10:30:00",  # Would use datetime.now() in real use
                "version": "1.0"
            }
            
            with open(filename, 'w') as f:
                json.dump(mission_data, f, indent=2)
            
            print(f"💾 Mission saved to {filename}")
            return True
        except Exception as e:
            print(f"❌ Failed to save mission: {e}")
            return False
    
    def load_mission(self, filename: str) -> bool:
        """Load mission from JSON file."""
        try:
            with open(filename, 'r') as f:
                mission_data = json.load(f)
            
            self.waypoints = mission_data.get("waypoints", [])
            print(f"📂 Mission loaded from {filename}")
            print(f"📍 Loaded {len(self.waypoints)} waypoints")
            return True
        except Exception as e:
            print(f"❌ Failed to load mission: {e}")
            return False
    
    def get_waypoints(self) -> List[Tuple[float, float, float]]:
        """Get the current waypoint list."""
        return self.waypoints.copy()

def interactive_mission_planner():
    """Interactive mission planning interface."""
    planner = MissionPlanner()
    
    print("🗺️ Interactive Mission Planner")
    print("=" * 40)
    print("Commands:")
    print("  add <lat> <lon> [alt]  - Add waypoint")
    print("  remove <index>        - Remove waypoint")
    print("  list                  - List waypoints")
    print("  summary               - Show mission summary")
    print("  validate              - Validate mission")
    print("  save <filename>       - Save mission to file")
    print("  load <filename>       - Load mission from file")
    print("  export                - Export for mission execution")
    print("  clear                 - Clear all waypoints")
    print("  quit                  - Exit planner")
    print()
    
    while True:
        try:
            command = input("Mission> ").strip().split()
            
            if not command:
                continue
            
            cmd = command[0].lower()
            
            if cmd == "quit" or cmd == "exit":
                break
            
            elif cmd == "add":
                if len(command) < 3:
                    print("Usage: add <lat> <lon> [alt]")
                    continue
                
                try:
                    lat = float(command[1])
                    lon = float(command[2])
                    alt = float(command[3]) if len(command) > 3 else 20.0
                    planner.add_waypoint(lat, lon, alt)
                except ValueError:
                    print("❌ Invalid coordinates")
            
            elif cmd == "remove":
                if len(command) < 2:
                    print("Usage: remove <index>")
                    continue
                
                try:
                    index = int(command[1]) - 1  # Convert to 0-based
                    planner.remove_waypoint(index)
                except ValueError:
                    print("❌ Invalid index")
            
            elif cmd == "list":
                waypoints = planner.get_waypoints()
                if waypoints:
                    print("\n📍 Current waypoints:")
                    for i, (lat, lon, alt) in enumerate(waypoints, 1):
                        print(f"   {i}: {lat:.6f}, {lon:.6f}, {alt}m")
                else:
                    print("No waypoints defined")
            
            elif cmd == "summary":
                planner.print_mission_summary()
            
            elif cmd == "validate":
                is_valid, issues = planner.validate_mission()
                if is_valid:
                    print("✅ Mission is valid")
                else:
                    print("⚠️ Mission issues:")
                    for issue in issues:
                        print(f"   - {issue}")
            
            elif cmd == "save":
                if len(command) < 2:
                    print("Usage: save <filename>")
                    continue
                
                filename = command[1]
                if not filename.endswith('.json'):
                    filename += '.json'
                
                planner.save_mission(filename)
            
            elif cmd == "load":
                if len(command) < 2:
                    print("Usage: load <filename>")
                    continue
                
                filename = command[1]
                if not filename.endswith('.json'):
                    filename += '.json'
                
                planner.load_mission(filename)
            
            elif cmd == "export":
                waypoints = planner.get_waypoints()
                if waypoints:
                    print("\n🚀 Mission ready for execution:")
                    print("Copy this waypoint list:")
                    print("waypoints = [")
                    for lat, lon, alt in waypoints:
                        print(f"    ({lat:.6f}, {lon:.6f}, {alt}),")
                    print("]")
                else:
                    print("❌ No waypoints to export")
            
            elif cmd == "clear":
                planner.waypoints.clear()
                print("🗑️ All waypoints cleared")
            
            else:
                print(f"❌ Unknown command: {cmd}")
        
        except KeyboardInterrupt:
            print("\n👋 Exiting mission planner")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("Mission planner closed")

def create_example_missions():
    """Create some example missions for testing."""
    
    # Example 1: Square pattern
    square_planner = MissionPlanner()
    square_planner.add_waypoint(28.459497, 77.026638, 20)  # Start
    square_planner.add_waypoint(28.459800, 77.026638, 20)  # North
    square_planner.add_waypoint(28.459800, 77.027000, 20)  # East
    square_planner.add_waypoint(28.459497, 77.027000, 20)  # South
    square_planner.add_waypoint(28.459497, 77.026638, 20)  # Return to start
    
    square_planner.save_mission("example_square_mission.json")
    print("📄 Created example_square_mission.json")
    
    # Example 2: Linear survey
    survey_planner = MissionPlanner()
    for i in range(5):
        lat = 28.459497 + (i * 0.0001)  # Move north
        survey_planner.add_waypoint(lat, 77.026638, 25)
    
    survey_planner.save_mission("example_survey_mission.json")
    print("📄 Created example_survey_mission.json")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "examples":
            create_example_missions()
        elif sys.argv[1] == "help":
            print(__doc__)
        else:
            print("Usage: python mission_planner.py [examples|help]")
    else:
        interactive_mission_planner()