from batch_interspire_analysis import BatchInterspireAnalyzer

def main():
    print("🚀 Starting initial analysis using EXISTING Interspire analyzers...")
    print("This will analyze all unanalyzed campaigns using your existing logic.")
    
    analyzer = BatchInterspireAnalyzer()
    
    # Get statistics
    stats = analyzer.get_analysis_statistics()
    print(f"📊 Statistics: {stats}")
    
    if stats['unanalyzed_campaigns'] == 0:
        print("✅ All campaigns already analyzed!")
        return
    
    confirm = input(f"Analyze {stats['unanalyzed_campaigns']} campaigns? (y/N): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return
    
    # Run batch analysis using EXISTING analyzers
    analyzer.run_batch_analysis(batch_size=50)
    
    print("✅ Initial analysis completed using existing analyzer logic!")

if __name__ == "__main__":
    main()
