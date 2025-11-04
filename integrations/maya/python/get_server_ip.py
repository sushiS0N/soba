"""
Helper script to find your PC's local IP address for network access
Run this on your PC to get the IP address to use on your laptop
"""

import socket
import subprocess
import platform


def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Create a socket and connect to an external address
        # This doesn't actually send data, just determines which interface would be used
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return None


def get_all_ips_windows():
    """Get all IP addresses on Windows using ipconfig"""
    try:
        result = subprocess.run(["ipconfig"], capture_output=True, text=True)
        lines = result.stdout.split("\n")

        ips = []
        current_adapter = None

        for line in lines:
            if "adapter" in line.lower():
                current_adapter = line.strip()
            elif "IPv4 Address" in line:
                # Extract IP from line like "   IPv4 Address. . . . . . . . . . : 192.168.1.100"
                ip = line.split(":")[-1].strip()
                if ip and current_adapter:
                    ips.append((current_adapter, ip))

        return ips
    except:
        return []


if __name__ == "__main__":
    print("=" * 70)
    print("SOLAR ANALYSIS - LOCAL NETWORK SETUP")
    print("=" * 70)
    print()

    # Get primary local IP
    primary_ip = get_local_ip()

    if primary_ip:
        print(f"✅ Your PC's Primary IP Address: {primary_ip}")
        print()
        print("📋 Configuration for laptop:")
        print("-" * 70)
        print(f"self.analysis_client = SolarAnalysisClient(")
        print(f'    server_url="http://{primary_ip}:8000",')
        print(f"    status_callback=self.on_status_update")
        print(f")")
        print("-" * 70)
        print()
        print(f"🌐 Test in browser on laptop: http://{primary_ip}:8000")
        print()
    else:
        print("⚠️  Could not detect primary IP")

    # Show all network adapters (Windows)
    if platform.system() == "Windows":
        print("\n📡 All Network Interfaces:")
        print("-" * 70)
        all_ips = get_all_ips_windows()

        if all_ips:
            for adapter, ip in all_ips:
                # Highlight WiFi adapter
                if "wi-fi" in adapter.lower() or "wireless" in adapter.lower():
                    print(f"  🔵 {ip:15} ← WiFi: {adapter}")
                else:
                    print(f"     {ip:15}    {adapter}")
        else:
            print("  Run 'ipconfig' manually to see all adapters")
        print("-" * 70)

    print()
    print("🔒 SECURITY:")
    print("   • Server only accessible on your local WiFi network")
    print("   • Not accessible from the internet")
    print("   • Your router's firewall provides protection")
    print()
    print("💡 NEXT STEPS:")
    print("   1. Copy the IP address above")
    print("   2. Update laptop's solarUI.py with this IP")
    print("   3. Make sure both devices are on the same WiFi")
    print("   4. Start server: python server.py")
    print("   5. Test from laptop!")
    print()
    print("=" * 70)
