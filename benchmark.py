#!/usr/bin/env python3
"""
Nebula Performance Benchmark Script

Orchestrates existing CLI commands to measure upload, download, streaming, and transcoding performance.

Usage:
    nebula benchmark /path/to/video.mp4
    python benchmark.py /path/to/video.mp4 --server http://localhost:8000

Requirements:
    - Python 3.7+
    - requests, tqdm (pip install requests tqdm)
    - nebula CLI installed
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

try:
    import requests
    from tqdm import tqdm
except ImportError:
    print("❌ Missing required packages. Install with: pip install requests tqdm")
    sys.exit(1)


class NebulaBenchmark:
    """Orchestrates Nebula CLI commands and measures performance"""

    def __init__(self, server_url: str, verbose: bool = False):
        self.server_url = server_url.rstrip('/')
        self.verbose = verbose
        self.session = requests.Session()

    def log(self, message: str):
        if self.verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get local file metadata"""
        path = Path(file_path)
        size_bytes = path.stat().st_size
        return {
            'path': str(path.absolute()),
            'filename': path.name,
            'size_bytes': size_bytes,
            'size_mb': size_bytes / (1024 * 1024)
        }

    def prepare_file(self, file_path: str) -> Tuple[str, Optional[str]]:
        """
        Prepare file for benchmarking - copy from /mnt/c/ to Linux temp if needed.
        Returns (actual_path, temp_path_to_cleanup)
        """
        if file_path.startswith('/mnt/'):
            self.log("WSL optimization: Copying file to Linux filesystem...")
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"nebula_bench_{os.getpid()}_{Path(file_path).name}")
            
            print(f"📋 Copying file from Windows to Linux temp (faster I/O)...")
            start = time.time()
            shutil.copy2(file_path, temp_path)
            copy_time = time.time() - start
            print(f"   Copied in {copy_time:.1f}s")
            
            return temp_path, temp_path
        return file_path, None

    def run_command(self, cmd: list, description: str, timeout: int = 600) -> Dict[str, Any]:
        """Run a CLI command and measure its execution time"""
        self.log(f"Running: {' '.join(cmd)}")
        
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            duration = time.time() - start_time
            
            return {
                'success': result.returncode == 0,
                'duration_seconds': duration,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return {
                'success': False,
                'duration_seconds': duration,
                'error': f'Timeout after {timeout}s'
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                'success': False,
                'duration_seconds': duration,
                'error': str(e)
            }

    def benchmark_upload(self, file_path: str) -> Dict[str, Any]:
        """Benchmark upload using nebula CLI"""
        file_info = self.get_file_info(file_path)
        print(f"\n📤 UPLOAD BENCHMARK")
        print(f"   File: {file_info['filename']} ({file_info['size_mb']:.1f} MB)")
        
        cmd = ['nebula', 'upload', file_path, '--description', 'Benchmark test file']
        result = self.run_command(cmd, "Upload", timeout=1800)  # 30 min timeout
        
        # Parse file ID from output
        file_id = None
        if result['success'] and result.get('stdout'):
            match = re.search(r'File ID:\s*(\d+)', result['stdout'])
            if match:
                file_id = int(match.group(1))
        
        throughput = (file_info['size_mb'] * 8) / result['duration_seconds'] if result['duration_seconds'] > 0 else 0
        
        return {
            'operation': 'upload',
            'success': result['success'],
            'file_id': file_id,
            'size_mb': file_info['size_mb'],
            'duration_seconds': result['duration_seconds'],
            'throughput_mbps': throughput,
            'error': result.get('error')
        }

    def benchmark_download(self, file_id: int, file_size_mb: float) -> Dict[str, Any]:
        """Benchmark download using nebula CLI"""
        print(f"\n📥 DOWNLOAD BENCHMARK")
        print(f"   File ID: {file_id}")
        
        # Download to temp directory
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"nebula_bench_download_{file_id}.tmp")
        
        cmd = ['nebula', 'download', str(file_id), '-o', output_path]
        result = self.run_command(cmd, "Download", timeout=1800)
        
        # Clean up downloaded file
        if os.path.exists(output_path):
            os.remove(output_path)
        
        throughput = (file_size_mb * 8) / result['duration_seconds'] if result['duration_seconds'] > 0 else 0
        
        return {
            'operation': 'download',
            'success': result['success'],
            'size_mb': file_size_mb,
            'duration_seconds': result['duration_seconds'],
            'throughput_mbps': throughput,
            'error': result.get('error')
        }

    def benchmark_stream(self, file_id: int, file_size_mb: float, range_bytes: Optional[int] = None) -> Dict[str, Any]:
        """Benchmark streaming by fetching data via HTTP (no player)"""
        if range_bytes:
            print(f"\n🎬 STREAM BENCHMARK (Range: {range_bytes/(1024*1024):.1f} MB)")
            headers = {'Range': f'bytes=0-{range_bytes}'}
            expected_mb = range_bytes / (1024 * 1024)
            op_name = 'stream_range'
        else:
            print(f"\n🎬 STREAM BENCHMARK (Full file)")
            headers = {}
            expected_mb = file_size_mb
            op_name = 'stream_full'
        
        url = f"{self.server_url}/api/files/{file_id}/stream"
        
        try:
            start_time = time.time()
            
            response = self.session.get(url, headers=headers, stream=True, timeout=1800)
            if response.status_code not in [200, 206]:
                raise Exception(f"HTTP {response.status_code}")
            
            # Stream and discard data (measuring throughput)
            downloaded = 0
            content_length = int(response.headers.get('Content-Length', 0))
            
            with tqdm(total=content_length, unit='B', unit_scale=True, desc="Streaming") as pbar:
                for chunk in response.iter_content(chunk_size=65536):  # 64KB chunks
                    if chunk:
                        downloaded += len(chunk)
                        pbar.update(len(chunk))
            
            duration = time.time() - start_time
            actual_mb = downloaded / (1024 * 1024)
            throughput = (actual_mb * 8) / duration if duration > 0 else 0
            
            return {
                'operation': op_name,
                'success': True,
                'size_mb': actual_mb,
                'duration_seconds': duration,
                'throughput_mbps': throughput,
                'status_code': response.status_code
            }
            
        except Exception as e:
            return {
                'operation': op_name,
                'success': False,
                'error': str(e),
                'duration_seconds': 0,
                'throughput_mbps': 0
            }

    def benchmark_transcode(self, file_id: int, qualities: list = None) -> Dict[str, Any]:
        """Benchmark transcoding - trigger and wait for completion"""
        if qualities is None:
            qualities = [480]  # Just 480p for quick benchmark
        
        print(f"\n🎥 TRANSCODE BENCHMARK")
        print(f"   File ID: {file_id}, Qualities: {qualities}")
        
        # Trigger transcoding via CLI
        quality_str = ','.join(map(str, qualities))
        cmd = ['nebula', 'transcode', str(file_id), '-q', quality_str]
        trigger_result = self.run_command(cmd, "Transcode trigger", timeout=30)
        
        if not trigger_result['success']:
            return {
                'operation': 'transcode',
                'success': False,
                'error': trigger_result.get('error', 'Failed to trigger transcoding'),
                'duration_seconds': trigger_result['duration_seconds']
            }
        
        # Poll for completion
        print("   Waiting for transcoding to complete...")
        start_time = time.time()
        timeout = 3600  # 1 hour max
        
        while time.time() - start_time < timeout:
            try:
                response = self.session.get(f"{self.server_url}/api/transcode/{file_id}", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    jobs = data.get('jobs', [])
                    
                    # Check if all jobs are done
                    pending = [j for j in jobs if j['status'] in ['pending', 'processing']]
                    completed = [j for j in jobs if j['status'] == 'completed']
                    failed = [j for j in jobs if j['status'] == 'failed']
                    
                    if not pending:
                        duration = time.time() - start_time
                        return {
                            'operation': 'transcode',
                            'success': len(failed) == 0,
                            'duration_seconds': duration,
                            'completed_jobs': len(completed),
                            'failed_jobs': len(failed),
                            'qualities': qualities
                        }
                    
                    # Show progress
                    for job in jobs:
                        if job['status'] == 'processing':
                            print(f"   {job['target_quality']}p: {job.get('progress', 0):.0f}%", end='\r')
                
                time.sleep(5)
                
            except Exception as e:
                self.log(f"Error polling transcode status: {e}")
                time.sleep(5)
        
        return {
            'operation': 'transcode',
            'success': False,
            'error': 'Timeout waiting for transcoding',
            'duration_seconds': time.time() - start_time
        }

    def run_full_benchmark(self, file_path: str, skip_transcode: bool = False) -> Dict[str, Any]:
        """Run complete benchmark suite"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'server_url': self.server_url,
            'file_info': self.get_file_info(file_path),
            'measurements': []
        }
        
        # Prepare file (WSL optimization)
        actual_path, temp_path = self.prepare_file(file_path)
        file_info = self.get_file_info(actual_path)
        
        try:
            # 1. Upload benchmark
            upload_result = self.benchmark_upload(actual_path)
            results['measurements'].append(upload_result)
            
            if not upload_result['success'] or not upload_result.get('file_id'):
                print(f"\n❌ Upload failed, cannot continue benchmark")
                return results
            
            file_id = upload_result['file_id']
            file_size_mb = file_info['size_mb']
            
            # 2. Download benchmark
            download_result = self.benchmark_download(file_id, file_size_mb)
            results['measurements'].append(download_result)
            
            # 3. Stream full file benchmark
            stream_full_result = self.benchmark_stream(file_id, file_size_mb)
            results['measurements'].append(stream_full_result)
            
            # 4. Stream range benchmark (first 50MB or file size, whichever is smaller)
            range_bytes = min(50 * 1024 * 1024, int(file_size_mb * 1024 * 1024))
            stream_range_result = self.benchmark_stream(file_id, file_size_mb, range_bytes)
            results['measurements'].append(stream_range_result)
            
            # 5. Transcode benchmark (optional)
            if not skip_transcode:
                transcode_result = self.benchmark_transcode(file_id, [480])
                results['measurements'].append(transcode_result)
            
        finally:
            # Cleanup temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
        
        return results

    def print_report(self, results: Dict[str, Any]):
        """Print formatted benchmark report"""
        print("\n" + "=" * 70)
        print("🚀 NEBULA PERFORMANCE BENCHMARK REPORT")
        print("=" * 70)
        
        file_info = results['file_info']
        print(f"\n📁 Test File: {file_info['filename']}")
        print(f"   Size: {file_info['size_mb']:.1f} MB")
        print(f"🔗 Server: {results['server_url']}")
        print(f"📅 Timestamp: {results['timestamp']}")
        
        print("\n" + "-" * 70)
        print("📊 RESULTS")
        print("-" * 70)
        
        for m in results['measurements']:
            op = m['operation'].replace('_', ' ').title()
            icon = "✅" if m['success'] else "❌"
            
            print(f"\n{icon} {op}")
            
            if m['success']:
                if 'throughput_mbps' in m and m['throughput_mbps'] > 0:
                    print(f"   Throughput: {m['throughput_mbps']:.1f} Mbps")
                if 'size_mb' in m:
                    print(f"   Data: {m['size_mb']:.1f} MB")
                if 'duration_seconds' in m:
                    print(f"   Duration: {m['duration_seconds']:.2f}s")
                if 'completed_jobs' in m:
                    print(f"   Jobs: {m['completed_jobs']} completed, {m.get('failed_jobs', 0)} failed")
            else:
                print(f"   Error: {m.get('error', 'Unknown error')}")
        
        # Summary insights
        print("\n" + "-" * 70)
        print("💡 INSIGHTS")
        print("-" * 70)
        
        measurements = {m['operation']: m for m in results['measurements']}
        
        upload = measurements.get('upload')
        download = measurements.get('download')
        stream = measurements.get('stream_full')
        
        if upload and download and upload['success'] and download['success']:
            ratio = download['throughput_mbps'] / upload['throughput_mbps'] if upload['throughput_mbps'] > 0 else 0
            print(f"\n📤 Upload: {upload['throughput_mbps']:.1f} Mbps")
            print(f"📥 Download: {download['throughput_mbps']:.1f} Mbps")
            if ratio < 0.8:
                print("   → Download slower than upload: Possible server/storage read bottleneck")
            elif ratio > 1.5:
                print("   → Download faster: Upload may be network-limited")
        
        if download and stream and download['success'] and stream['success']:
            ratio = stream['throughput_mbps'] / download['throughput_mbps'] if download['throughput_mbps'] > 0 else 0
            print(f"\n🎬 Stream: {stream['throughput_mbps']:.1f} Mbps")
            if ratio < 0.9:
                print(f"   → Streaming {(1-ratio)*100:.0f}% slower than download: Range handling overhead")
        
        print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Nebula Cloud performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nebula benchmark /path/to/video.mp4
  python benchmark.py /path/to/video.mp4 --server http://192.168.1.100:8000
  python benchmark.py /path/to/video.mp4 --skip-transcode --verbose
        """
    )
    parser.add_argument("file_path", help="Path to video file to benchmark")
    parser.add_argument("--server", help="Nebula server URL (default: NEBULA_SERVER_URL env var)")
    parser.add_argument("--skip-transcode", action="store_true", help="Skip transcoding benchmark")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--output", "-o", help="Save results to JSON file")
    
    args = parser.parse_args()
    
    # Get server URL
    server_url = args.server or os.getenv("NEBULA_SERVER_URL", "http://localhost:8000")
    
    # Validate file exists
    if not os.path.exists(args.file_path):
        print(f"❌ File not found: {args.file_path}")
        sys.exit(1)
    
    # Check nebula CLI is available
    if not shutil.which("nebula"):
        print("❌ 'nebula' CLI not found. Make sure it's installed and in PATH.")
        sys.exit(1)
    
    print("🚀 Starting Nebula Performance Benchmark...")
    print(f"📁 File: {args.file_path}")
    print(f"🔗 Server: {server_url}")
    
    benchmark = NebulaBenchmark(server_url, args.verbose)
    
    try:
        results = benchmark.run_full_benchmark(args.file_path, skip_transcode=args.skip_transcode)
        benchmark.print_report(results)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {args.output}")
            
    except KeyboardInterrupt:
        print("\n⚠️ Benchmark interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
