import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
from supabase import create_client
import random

# Initialize Supabase client
# You'll need to replace these with your actual Supabase credentials
SUPABASE_URL = "https://zhapyptsggkznsafupuv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpoYXB5cHRzZ2drem5zYWZ1cHV2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDA4OTYyNTcsImV4cCI6MjA1NjQ3MjI1N30.dwhONFfkwIr8tjbXcK6Hik7WlmslqA9g3U6Y0jNd5X0"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Set page config
st.set_page_config(
    page_title="Seattle Event Swiper",
    page_icon="🎭",
    layout="centered"
)

# Initialize session state variables if they don't exist
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'current_event_index' not in st.session_state:
    st.session_state.current_event_index = 0
if 'events' not in st.session_state:
    st.session_state.events = []
if 'notification' not in st.session_state:
    st.session_state.notification = None

def scrape_event_details(event_url):
    """
    Scrape detailed information from an individual event page on EverOut
    
    Args:
        event_url (str): URL of the event detail page
        
    Returns:
        dict: Dictionary containing detailed event information
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        response = requests.get(event_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Extract event title
        title = soup.find('h1')
        event_name = title.text.strip() if title else "Unknown Event"
        
        # Extract event details
        event_info = soup.find('div', class_='event-info')
        
        # Initialize variables
        event_date = "Date not available"
        event_location = "Location not available"
        event_price = "Price not available"
        event_age = "Age restrictions not available"
        event_ticket_link = None
        event_description = "Description not available"
        event_image = None
        
        if event_info:
            # Date information
            date_div = event_info.find('div', class_='date-summary')
            if date_div:
                event_date = date_div.text.strip().replace('\n', ' ').strip()
                # Clean up the date by removing the icon text
                if "calendar" in event_date.lower():
                    event_date = ' '.join(event_date.split()[1:])
            
            # Location information
            location_div = event_info.find('div', class_='location')
            if location_div:
                location_link = location_div.find('a')
                if location_link:
                    event_location = location_link.text.strip()
            
            # Price information
            price_div = event_info.find('div', class_='price')
            if price_div:
                event_price = price_div.text.strip()
                if "receipt" in event_price.lower():
                    event_price = ' '.join(event_price.split()[1:])
            
            # Age restrictions
            age_div = event_info.find('div', class_='age-restrictions')
            if age_div:
                event_age = age_div.text.strip()
                if "child" in event_age.lower():
                    event_age = ' '.join(event_age.split()[1:])
            
            # Ticket link
            ticket_div = event_info.find('div', class_='get-tickets')
            if ticket_div:
                ticket_link = ticket_div.find('a')
                if ticket_link and ticket_link.has_attr('href'):
                    event_ticket_link = ticket_link['href']
        
        # Get event description
        description_div = soup.find('div', class_='descriptions')
        if description_div:
            desc_content = description_div.find('div', class_='description')
            if desc_content:
                # Get all paragraph text
                paragraphs = desc_content.find_all('p')
                desc_texts = [p.text.strip() for p in paragraphs]
                # Skip the first paragraph if it's just an attribution note
                if desc_texts and "following description comes from" in desc_texts[0]:
                    desc_texts = desc_texts[1:]
                event_description = ' '.join(desc_texts)
        
        # Get event image
        image_div = soup.find('div', class_='item-image')
        if image_div:
            img = image_div.find('img')
            if img and img.has_attr('src'):
                event_image = img['src']
        
        # Compile all information
        event_details = {
            "name": event_name,
            "date": event_date,
            "location": event_location,
            # "price": event_price,
            # "age_restriction": event_age,
            # "ticket_link": event_ticket_link,
            "description": event_description,
            "image": event_image,
            "link": event_url
        }
        
        return event_details
    
    except Exception as e:
        print(f"Error scraping event details: {e}")
        return None

# Function to get links from the home page and then scrape each event detail
def scrape_all_events():
    home_url = "https://everout.com/seattle/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    events_list = []
    
    try:
        # First get event links from the home page
        response = requests.get(home_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Find links that look like event links
        potential_links = []
        for link in soup.find_all('a'):
            href = link.get('href', '')
            # Look for URLs that match event patterns
            if '/events/' in href and '/e' in href:
                if not href.startswith('http'):
                    href = f"https://everout.com{href}"
                potential_links.append(href)
        
        # Limit to first 10-20 events to avoid overloading
        event_links = potential_links
        
        links = set({})
        # Process each event link
        for i, link in enumerate(event_links):
            if link in links:
                continue
            # print(f"Scraping event {i+1}/{len(event_links)}: {link}")
            event_details = scrape_event_details(link)
            
            if event_details:
                # Add an ID for database storage
                event_details["id"] = i + 1
                events_list.append(event_details)
                
                # Pause between requests to be respectful
                time.sleep(1)

            links.add(link)
        
        return events_list
        
    except Exception as e:
        print(f"Error during event scraping: {e}")
        return []

# Function to save event to database
def save_event_preference(user, event_id, interested):
    # Check if user already has a preference for this event
    response = supabase.table('user_events').select('*').eq('username', user).eq('event_id', event_id).execute()
    
    # If user already has a preference, update it
    if response.data:
        supabase.table('user_events').update({"interested": interested}).eq('username', user).eq('event_id', event_id).execute()
    # Otherwise, insert a new record
    else:
        supabase.table('user_events').insert({'username': user, "event_id": event_id, "interested": interested}).execute()
    
    # Check if this creates a match
    check_for_match(event_id)

# Function to check if there's a match for an event
def check_for_match(event_id):
    # Get both users' preferences for this event
    andy_response = supabase.table('user_events').select('interested').eq('username', 'Andy').eq('event_id', event_id).execute()
    linh_response = supabase.table('user_events').select('interested').eq('username', 'Linh Dan').eq('event_id', event_id).execute()
    
    # Check if both users are interested
    if andy_response.data and linh_response.data:
        if andy_response.data[0]['interested'] and linh_response.data[0]['interested']:
            # Get event details
            event_response = supabase.table('events').select('name').eq('id', event_id).execute()
            if event_response.data:
                event_name = event_response.data[0]['name']
                st.session_state.notification = f"Match! Both Andy and Linh Dan want to go to {event_name}!"

# Function to get all saved events for a specific user or both
def get_saved_events(user=None):
    if user == "Both":
        # Get events both users are interested in
        andy_events = supabase.table('user_events').select('event_id').eq('username', 'Andy').eq('interested', True).execute()
        linh_events = supabase.table('user_events').select('event_id').eq('username', 'Linh Dan').eq('interested', True).execute()
        
        # Find common event_ids
        andy_event_ids = [event['event_id'] for event in andy_events.data]
        linh_event_ids = [event['event_id'] for event in linh_events.data]
        common_event_ids = list(set(andy_event_ids) & set(linh_event_ids))
        
        # Get event details for common events
        if common_event_ids:
            events = supabase.table('events').select('*').in_('id', common_event_ids).execute()
            return events.data
        return []
    
    elif user:
        # Get events a specific user is interested in
        user_events = supabase.table('user_events').select('event_id').eq('username', user).eq('interested', True).execute()
        event_ids = [event['event_id'] for event in user_events.data]
        
        if event_ids:
            events = supabase.table('events').select('*').in_('id', event_ids).execute()
            return events.data
        return []
    
    else:
        # Get all events
        events = supabase.table('events').select('*').execute()
        return events.data

# Function to handle swipe left (not interested)
def swipe_left():
    if st.session_state.current_event_index < len(st.session_state.events):
        event = st.session_state.events[st.session_state.current_event_index]
        save_event_preference(st.session_state.current_user, event['id'], False)
        st.session_state.current_event_index += 1

# Function to handle swipe right (interested)
def swipe_right():
    if st.session_state.current_event_index < len(st.session_state.events):
        event = st.session_state.events[st.session_state.current_event_index]
        save_event_preference(st.session_state.current_user, event['id'], True)
        st.session_state.current_event_index += 1

# Function to save events to database
def save_events_to_db(events):
    for event in events:
        # Check if event already exists in database
        response = supabase.table('events').select('*').eq('name', event['name']).execute()
        
        # If event doesn't exist, insert it
        if not response.data:
            supabase.table('events').insert(event).execute()

# Function to reset swiping session
def reset_swiping():
    st.session_state.current_event_index = 0

# Main UI
def main():
    st.title("Seattle Event Swiper 🎭")
    
    # Setup tabs
    tab1, tab2 = st.tabs(["Swipe Events", "Saved Events"])
    
    with tab1:
        # User selection
        if not st.session_state.current_user:
            st.header("Who are you?")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Andy", use_container_width=True):
                    st.session_state.current_user = "Andy"
                    # Reset the event index when user changes
                    reset_swiping()
                    st.rerun()
            
            with col2:
                if st.button("Linh Dan", use_container_width=True):
                    st.session_state.current_user = "Linh Dan"
                    # Reset the event index when user changes
                    reset_swiping()
                    st.rerun()
        
        # Event swiping interface
        else:
            # Display notification if there's a match
            if st.session_state.notification:
                st.success(st.session_state.notification)
                # Clear notification after displaying
                if st.button("Clear Notification"):
                    st.session_state.notification = None
            
            st.subheader(f"Welcome, {st.session_state.current_user}!")
            
            # Button to switch user
            if st.button("Switch User"):
                st.session_state.current_user = None
                reset_swiping()
                st.rerun()
            
            # Check if we have events
            if not st.session_state.events:
                with st.spinner("Loading events..."):
                    # Try to get events from database first
                    db_events = get_saved_events()
                    
                    # If there are fewer than 10 events in the database, scrape for more
                    if len(db_events) < 10:
                        st.session_state.events = scrape_all_events()
                        # Save new events to database
                        save_events_to_db(st.session_state.events)
                    else:
                        st.session_state.events = db_events
                    
                    # Shuffle events to make it more interesting
                    random.shuffle(st.session_state.events)
            
            # Display events for swiping
            if st.session_state.current_event_index < len(st.session_state.events):
                event = st.session_state.events[st.session_state.current_event_index]
                
                # Display event card
                with st.container():
                    if event['image']:
                        st.image(event['image'], width=300)
                    st.markdown(f"### {event['name']}")
                    st.markdown(f"**Date:** {event['date']}")
                    st.markdown(f"**Location:** {event['location']}")
                    
                    with st.expander("Show Description"):
                        st.markdown(event['description'])
                        st.markdown(f"[Event Link]({event['link']})")
                
                # Swipe buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("👎 Not Interested", use_container_width=True):
                        swipe_left()
                        st.rerun()
                
                with col2:
                    if st.button("👍 Interested", use_container_width=True):
                        swipe_right()
                        st.rerun()
            
            else:
                st.success("You've gone through all available events!")
                if st.button("Start Over"):
                    reset_swiping()
                    st.session_state.events = []
                    st.rerun()
    
    with tab2:
        st.header("Saved Events")
        
        # Filter options
        filter_option = st.selectbox(
            "Filter events by:",
            options=["Both", "Andy", "Linh Dan"]
        )
        
        # Get filtered events
        filtered_events = get_saved_events(filter_option)
        
        if filtered_events:
            for event in filtered_events:
                with st.container():
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        st.image(event['image'], width=150)
                    
                    with col2:
                        st.markdown(f"### {event['name']}")
                        st.markdown(f"**Date:** {event['date']}")
                        st.markdown(f"**Location:** {event['location']}")
                        
                        with st.expander("Show Description"):
                            st.markdown(event['description'])
                            st.markdown(f"[Event Link]({event['link']})")
                
                st.divider()
        else:
            if filter_option == "Both":
                st.info("No events have been saved by both users yet.")
            else:
                st.info(f"No events have been saved by {filter_option} yet.")

# Setup database and run the app
if __name__ == "__main__":
    main()